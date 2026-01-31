-- Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
-- SPDX-License-Identifier: MIT

mustechSwitch.lua
----------------------
socket = require("socket")
udp    = assert(socket.udp())
os     = require("os")
local https  = require( "ssl.https" )


function log( timestamp, msg )

   if doLog then
--      obsv.log( timestamp, msg );
      obsv.writeJson( timestamp, "\"date\":\""..obsv.timestamp('%c',timestamp).."\",".. msg );
   end

end

function printf( timestamp, msg )

   print( "(Lua) " .. obsv.timestamp('%c',timestamp) .. ": [" .. obsv.name .. "] " .. msg )

end

function tominsec( duration )
   sec = math.fmod( duration, 60 )
   min = math.floor(duration / 60.0 )
   if min == 0 then
      return string.format( "%02d", sec )
   end

   return string.format( "%02d:%02d", min, sec )
end

function init( timestamp )

   verbose     = obsv.param.bool( "verbose", true )
   sandbox     = obsv.param.bool( "sandbox", false )
   resend      = obsv.param.bool( "resend",  true );
   maxFPS      = obsv.param.number("maxFPS",2.0);
   enterDelay  = obsv.param.number("enterDelay",0.0); -- sec before switching on
   leaveDelay  = obsv.param.number("leaveDelay",0.0); -- sec before switching off
   minOnTime   = obsv.param.number("minOnTime",0.0);  -- min sec on
   minOffTime  = obsv.param.number("minOffTime",0.0); -- min sec off
   cycle       = obsv.param.bool  ( "cycle", false ); -- if true then it is switched off after a multiple of minOnTime
   protocol    = obsv.param.number("protocol","");    -- set protocol
   runMode     = obsv.param.string("runMode","");

   host        = obsv.param.string ("host","");
   port        = obsv.param.integer("port",0);
   url         = obsv.param.string ("url","");

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

   doLog       = obsv.logFileName() ~= "" and runMode == "production"

   if verbose then
      printf( timestamp, "enterDelay: " .. tostring(enterDelay) )
      printf( timestamp, "leaveDelay: " .. tostring(leaveDelay) )
      printf( timestamp, "minOnTime:  " .. tostring(minOnTime) )
      printf( timestamp, "minOffTime: " .. tostring(minOffTime) )
      printf( timestamp, "cycle:      " .. tostring(cycle) )
      if doLog then
     printf( timestamp, "logging to file: " .. obsv.logFileName() )
      end
   end

end

function sendStatus( objects, status, timestamp )

   if protocol == "udp" then
      local msg = "lidar/switch " .. objects:regionName() .. " " .. tostring(status and 1 or 0) .. "\n";
      if not sandbox then
     udp:send( msg )
      end
      if verbose then
     local resendMsg = objects.resend and " resend" or ""
     printf( timestamp, "send(" .. host .. ":" .. port .. "): " .. msg .. resendMsg )
      end
   else
      local reqUrl = status and url.."on" or url.."off";
      if verbose then
     local resendMsg = objects.resend and " resend" or ""
     printf( timestamp, "get( " .. reqUrl .. " )".. resendMsg )
      end
--      printf( timestamp, "requrl: " .. reqUrl )
      if not sandbox then
     local headers  = { [ "guardian-password" ] = pwd, }
     client, code, headers, status = https.request{ url=reqUrl, headers=headers }
      end
--      print( code )
   end
end

function setOn( objects, set, timestamp )

   objects.isOn           = set
   objects.lastShouldBeOn = set
   objects.stateTime      = os.time(os.date('*t'))
   objects.onOffTime      = objects.stateTime

   if set then
      objects.totalOffMSec = objects.totalOffMSec + (timestamp-objects.onChangedTimestamp)
      log( timestamp, "\"switch\":\"on\"" );
      obsv.setStatusMsg( "["..obsv.name.."]  on" )
   else
      objects.totalOnMSec  = objects.totalOnMSec  + (timestamp-objects.onChangedTimestamp)
      log( timestamp, "\"switch\":\"off\"" );
      obsv.setStatusMsg( "["..obsv.name.."] off" )
   end

   objects.onChangedTimestamp = timestamp

   sendStatus( objects, set, timestamp )
   objects.resend = resend
end


function objectsObserve( objects, timestamp )

   if objects.resend then
      sendStatus( objects, objects.isOn, timestamp )
      objects.resend = false
   end

   local localTime     = os.time(os.date('*t'))
   local switch        = objects:switch( false )
   local shouldBeOn    = switch

--   print( "shouldBeOn: " .. tostring(shouldBeOn) .. " stateTimeDiff: " .. tostring(stateTimeDiff) )

   if shouldBeOn ~= objects.lastShouldBeOn then
      objects.stateTime      = localTime
      objects.lastShouldBeOn = shouldBeOn
   end

   local stateTimeDiff = localTime - objects.stateTime;
   if (shouldBeOn and stateTimeDiff >= enterDelay) or ((not shouldBeOn) and stateTimeDiff >= leaveDelay) then
      local onOffTimeDiff = localTime - objects.onOffTime
      if (objects.isOn and onOffTimeDiff >= minOnTime) or ((not objects.isOn) and onOffTimeDiff >= minOffTime) then
     objects.shouldBeOn = shouldBeOn
      end
   end

   shouldBeOn = objects.shouldBeOn

   if shouldBeOn and minOnTime > 0 then
      local onOffTimeDiff = localTime - objects.onOffTime
      if cycle and onOffTimeDiff >= minOnTime then
     objects.onOffTime = objects.onOffTime + minOnTime
     onOffTimeDiff     = localTime - objects.onOffTime
      end
      if minOnTime-onOffTimeDiff > 0 then
     obsv.setStatusMsg( "["..obsv.name.."] " .. tominsec(minOnTime-onOffTimeDiff) )
      else
     obsv.setStatusMsg( "["..obsv.name.."]  on" )
      end
   end

   if shouldBeOn ~= objects.isOn then
      setOn( objects, shouldBeOn, timestamp )
   end

end

function objectsStart( objects, timestamp )

   objects.startTimestamp     = timestamp
   objects.onChangedTimestamp = timestamp
   objects.shouldBeOn         = false;
   objects.totalOnMSec        = 0
   objects.totalOffMSec       = 0
   objects.resend             = false

   setOn( objects, false, timestamp )

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

---------------
observer.txt
---------------
luaFPS=2

verb=0

enterDelay=0
leaveDelay=3
minOnTime=5
minOffTime=1

#
#sammlung-frequencies-rampe-links.zkm.de
#sammlung-frequencies-rampe-rechts.zkm.de
#sammlung-frequencies-rampe-sub.zkm.de
#sammlung-lafontaine-rampe.zkm.de

steuerung="@type=lua @verbose=$verb @maxFPS=$luaFPS @enterDelay=$enterDelay @leaveDelay=$leaveDelay @minOnTime=$minOnTime @minOffTime=$minOffTime @runMode=$runMode @script=conf/sammlung/mustechSwitch.lua @pwd=$(cat projPasswd.txt) @url=https://steuerung.mutech.zkm.de/api/work"

#Haaslahti:
# https://steuerung.mutech.zkm.de/api/work/94b248a7-a7bc-44a9-ade4-277c90339b44/
region=haaslahti
observer+=(+observer @name=$region @regions=$region @file=conf/sammlung/operation/$region/${region}_operation_%daily.log $steuerung/94b248a7-a7bc-44a9-ade4-277c90339b44/)

#Neugebauer
# https://steuerung.mutech.zkm.de/api/work/000f7ca7-e70d-4664-b10d-16a57709abe8/
region=neugebauer
observer+=(+observer @name=$region @regions=$region @file=conf/sammlung/operation/$region/${region}_operation_%daily.log $steuerung/000f7ca7-e70d-4664-b10d-16a57709abe8/ @minOnTime=170 @cycle=1)

#Gonzalez:
# https://steuerung.mutech.zkm.de/api/work/cdbe46d5-030f-4755-8dff-f143d32fc99f/
region=gonzalez
observer+=(+observer @name=$region @regions=$region @file=conf/sammlung/operation/$region/${region}_operation_%daily.log $steuerung/cdbe46d5-030f-4755-8dff-f143d32fc99f/ @minOnTime=630 @cycle=1)

#Mariotti:
# https://steuerung.mutech.zkm.de/api/work/052f3ab8-5c30-4829-9b62-f59757262626/
region=mariotti
observer+=(+observer @name=$region @regions=mariotti1,mariotti2=mariotti @file=conf/sammlung/operation/$region/${region}_operation_%daily.log $steuerung/052f3ab8-5c30-4829-9b62-f59757262626/ @minOnTime=30)

#Lafontaine:
# https://steuerung.mutech.zkm.de/api/work/12316ac6-4cb1-4814-add9-ec124ce341eb/
region=lafontaine
observer+=(+observer @name=$region @regions=$region @file=conf/sammlung/operation/$region/${region}_operation_%daily.log $steuerung/12316ac6-4cb1-4814-add9-ec124ce341eb/)

#Bernier:
# https://steuerung.mutech.zkm.de/api/work/e628f6b6-c359-4b2f-94a0-835f6333c5a6/
region=bernier
observer+=(+observer @name=$region @regions=$region @file=conf/sammlung/operation/$region/${region}_operation_%daily.log $steuerung/e628f6b6-c359-4b2f-94a0-835f6333c5a6/)


