-- Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
-- SPDX-License-Identifier: MIT
socket = require("socket")
udp    = assert(socket.udp())
os     = require("os")
local https  = require( "ssl.https" )

function log( timestamp, msg )
      
   if doLog then
--      obsv.log( timestamp, msg );
      obsv.log( timestamp, "\"date\":\""..obsv.timestamp('%c',timestamp).."\",".. msg );
   end
   
end

function printf( timestamp, msg )
      
   print( "(Lua) " .. obsv.timestamp('%c',timestamp) .. ": [" .. obsv.name .. "] " .. msg )

end

function totimestring( sec )
    
   local min = math.floor( sec / 60 )
   sec = math.floor( math.fmod( sec, 60 ) )

   local string = tostring(min) .. ":" .. tostring(sec)
   return string

end

function init( timestamp )

   verbose     = obsv.param.bool( "verbose", true )
   resend      = obsv.param.bool( "resend",  true );
   maxFPS      = obsv.param.number("maxFPS",15.0);
   enterDelay  = obsv.param.number("enterDelay",0.0);   -- sec before switching on
   leaveDelay  = obsv.param.number("leaveDelay",0.0);   -- sec before switching off
   minOnTime   = obsv.param.number("minOnTime",0.0);    -- min sec on
   minOffTime  = obsv.param.number("minOffTime",0.0);   -- min sec off
   leaveDelay  = obsv.param.number("leaveDelay",0.0);   -- sec before switching off
   minBudget   = obsv.param.number("minBudget",0.0);    -- min sec left to switch on
   sliceSize   = obsv.param.number("sliceSize",30.0);   -- sec per slice
   sliceBudget = obsv.param.number("sliceBudget",10.0); -- sec budget per slice
   protocol    = obsv.param.number("protocol","");      -- set protocol
   runMode     = obsv.param.string("runMode","");

   host        = obsv.param.string("host","");
   port        = obsv.param.integer("port",0);
   url         = obsv.param.string("url","");

   serverport  = obsv.param.integer("serverport",0);

   if serverport > 0 then
      BACKLOG=5
      server=assert(socket.tcp())
      assert(server:bind("*", serverport))
      server:listen(BACKLOG)
      server:settimeout(0)

      ip, port = server:getsockname()
      if verbose then
	 printf( timestamp, "Listening on IP="..ip..", PORT="..port.."...")
      end
   end

   doLog       = obsv.logFileName() ~= "" and runMode == "production"

   if protocol == "" then
      if host ~= "" then
	 protocol = "udp"
      else
	 protocol = "https"
      end
   end

   if protocol == "udp" then
      if verbose then
	 printf( timestamp, "connecting to host " .. host .. ":" .. port )
      end
      udp:settimeout(1)
      assert(udp:setsockname("*",0))
      assert(udp:setpeername(host, port))
   else
      pwd      = obsv.param.string("pwd","");
      headers  = { [ "guardian-password" ] = pwd, }
      if verbose then
	 printf( timestamp, "using url " .. url )
      end
   end

   if verbose then
      printf( timestamp, "enterDelay:  " .. tostring(enterDelay) )
      printf( timestamp, "leaveDelay:  " .. tostring(leaveDelay) )
      printf( timestamp, "minOnTime:   " .. tostring(minOnTime) )
      printf( timestamp, "minOffTime:  " .. tostring(minOffTime) )
      printf( timestamp, "minBudget:   " .. tostring(minBudget) )
      printf( timestamp, "sliceSize:   " .. tostring(sliceSize) )
      printf( timestamp, "sliceBudget: " .. tostring(sliceBudget) )
   end

end

function sendStatus( objects, status, timestamp )

   if protocol == "udp" then
      local msg = "lidar/switch " .. objects:regionName() .. " " .. tostring(status and 1 or 0) .. "\n";
      udp:send( msg )
      if verbose then
	 local resendMsg = objects.resend and " resend" or ""
	 printf( timestamp, "send(" .. host .. ":" .. port .. "): " .. msg .. resendMsg )
      end
   else
      local reqUrl = status and url.."on" or url.."off";
      if verbose then
	 local resendMsg = objects.resend and " resend" or ""
	 printf( timestamp, "get( " .. reqUrl .. " )" .. resendMsg )
      end
--      print( "requrl: " .. reqUrl )
      local headers  = { [ "guardian-password" ] = pwd, }
      client, code, headers, status = https.request{ url=reqUrl, headers=headers }
--      print( code )
   end
end

function setOn( objects, set, timestamp )

   objects.isOn       = set
   objects.time       = os.time(os.date('*t'))
   objects.onOffTime  = objects.time
   
   if set then
      objects.totalOffMSec = objects.totalOffMSec + (timestamp-objects.onChangedTimestamp)
      log( timestamp, "\"switch\":\"on\"" );
   else
      objects.totalOnMSec  = objects.totalOnMSec  + (timestamp-objects.onChangedTimestamp)
      log( timestamp, "\"switch\":\"off\"" );
   end

   objects.onChangedTimestamp = timestamp

   sendStatus( objects, set, timestamp )
   objects.resend   = resend

   local secToSlice = math.floor( sliceSize - objects.time % sliceSize )
   local msg = "left=" .. totimestring(math.floor(objects.budget)) .. " next=" .. totimestring(secToSlice) .. " ["..obsv.name.."] "
   if set then
      msg = msg .. "on"
   else
      msg = msg .. "off"
   end

   obsv.setStatusMsg( msg )

end


function objectsObserve( objects, timestamp )

   if objects.resend then 
      sendStatus( objects, objects.isOn, timestamp )
      objects.resend = false
   end

   local localTime  = os.time(os.date('*t'))
   local sliceIndex = math.floor(localTime / sliceSize)

   if sliceIndex ~= objects.lastSlice then
      objects.budget    = sliceBudget
      objects.time      = localTime
      objects.lastSlice = sliceIndex
   end

   local switch        = objects:switch( false )
   local shouldBeOn    = switch

   if shouldBeOn ~= objects.lastShouldBeOn then
      objects.stateTime      = localTime
      objects.lastShouldBeOn = shouldBeOn
   end

   local timeDiff      = localTime - objects.time
   local stateTimeDiff = localTime - objects.stateTime
   local budgetDiff    = (objects.isOn and timeDiff or 0)
   local budgetLeft    = objects.budget - budgetDiff
   local stateTimeDiff = localTime - objects.stateTime;

   if (shouldBeOn and stateTimeDiff >= enterDelay) or ((not shouldBeOn) and stateTimeDiff >= leaveDelay) then
--      print( "set shouldBeOn: " .. tostring(shouldBeOn) .. " timeDiff: " .. tostring(timeDiff) .. " stateTimeDiff: " .. tostring(stateTimeDiff) )

      local onOffTimeDiff = localTime - objects.onOffTime
      if (objects.isOn and onOffTimeDiff >= minOnTime) or ((not objects.isOn) and onOffTimeDiff >= minOffTime) then
	 objects.shouldBeOn = shouldBeOn
      end
   end

   if objects.isOn then
      shouldBeOn = (objects.shouldBeOn and budgetLeft > 0)
   else
      shouldBeOn = (objects.shouldBeOn and budgetLeft > minBudget)
   end

--   print( "budget: " .. tostring(budgetLeft) )
--   print( "shouldBeOn: " .. tostring(shouldBeOn) .. " timeDiff: " .. tostring(timeDiff) .. " stateTimeDiff: " .. tostring(stateTimeDiff) )

   local budget     = math.floor( budgetLeft )
   local secToSlice = math.floor( sliceSize - localTime % sliceSize )

   if shouldBeOn ~= objects.isOn then
      if not shouldBeOn then
	 objects.budget = budgetLeft
      end
      setOn( objects, shouldBeOn, timestamp )
   else
      local msg = "left=" .. totimestring(budget) .. " next=" .. totimestring(secToSlice) .. " ["..obsv.name.."] "
      if shouldBeOn then
	 msg = msg .. "on"
      else
	 msg = msg .. "off"
      end
      obsv.setStatusMsg( msg )
   end


   if timestamp - objects.logTimestamp > 1000 then
      local hasServer = server:getfd()
      printf( timestamp, "server open: " .. tostring(hasServer) )
      objects.logTimestamp = timestamp
   end

   if server then
      
      repeat
	 local client,err = server:accept()

	 if client then
	    local line, err = client:receive()
	    if err then
	       printf( timestamp, "error receiving line: " .. line )
	    else
	       printf( timestamp, "received line: " .. line )

	       if string.find( line, "json" ) then

		  if not objects.isOn and budgetLeft <= minBudget then
		     budgetLeft = 0
		  end
		  local json = "\"budget\":" .. tostring(budget) .. ", \"secToSlice\":" .. tostring(secToSlice)
		  printf( timestamp, "sending json: " .. json )
		  client:send("HTTP/1.0 200 OK\nContent-Type: application/json\nAccess-Control-Allow-Origin: *\nX-XSS-Protection: 0\n\n{" .. json .. "}")
	       else
		  local html
		  if budgetLeft <= minBudget then
		     html = "time to wait: " .. totimestring(secToSlice)
		  else
		     html = "time left: " .. totimestring(budget)
		  end
		  printf( timestamp, "sending html: " .. html )
		  client:send("HTTP/1.0 200 OK\nContent-Type: text/html\nAccess-Control-Allow-Origin: *\nX-XSS-Protection: 0\n\n" .. html )
	       end
	    end
	    client:close()
	 end

      until not client
   end

end

function objectsStart( objects, timestamp )
      
   objects.budget         = sliceBudget
   objects.shouldBeOn     = false
   objects.lastShouldBeOn = objects.shouldBeOn
   objects.stateTime      = os.time(os.date('*t'))

   objects.startTimestamp     = timestamp
   objects.onChangedTimestamp = timestamp
   objects.totalOnMSec        = 0
   objects.totalOffMSec       = 0
   objects.resend             = false

   setOn( objects, false, timestamp )

   objects.logTimestamp       = timestamp
end

function objectsStop( objects, timestamp )

   if objects.isOn then
      setOn( objects, false, timestamp )
   end

   if doLog then
      log( timestamp, "\"totalMSec\":"..tostring(timestamp-objects.startTimestamp)..", \"onMSec\":"..tostring(objects.totalOnMSec)..", \"offMSec\":"..tostring(objects.totalOffMSec)..", \"onFraction\":"..tostring(objects.totalOnMSec/(timestamp-objects.startTimestamp)) );
   end

   if objects.resend then 
      sendStatus( objects, objects.isOn, timestamp )
      objects.resend = false
   end

end

function start( timestamp )

   log( timestamp, "\"action\":\"start\"" )

end

function stop( timestamp )

   log( timestamp, "\"action\":\"stop\"" );

end


