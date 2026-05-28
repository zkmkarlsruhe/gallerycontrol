# Troubleshooting

## Device Not Responding

1. Check network connectivity:
   ```bash
   ping <device-ip>
   ```

2. Verify port is open:
   ```bash
   nc -zv <device-ip> <port>
   ```
   - PJLink: port 4352
   - NETIO: port 80
   - ANEL: via runner

3. Check device logs in Logs view

4. Try direct API query:
   ```bash
   curl http://localhost:8000/api/debug/device/{id}/info
   ```

---

## State Not Updating

1. Check SSE connection in browser DevTools (Network tab, filter EventStream)

2. Verify device is enabled in Edit Mode

3. Check State Monitor logs for errors

4. Force refresh: Clear browser cache or hard reload (Ctrl+Shift+R)

5. Check if device is in cooldown (poll progress bar shows time remaining)

---

## Schedule Not Running

1. Check job status in Admin panel - look for "Circuit Open" badge

2. Verify cron expression syntax at [crontab.guru](https://crontab.guru)

3. Check `schedules_enabled` on target artwork/exhibition

4. Look for circuit breaker (fail_count ≥ 5)

5. Check scheduler logs for errors

---

## Database Connection Issues

```bash
# Test connection
psql -h localhost -U gallerycontrol -d gallerycontrol -c "SELECT 1"

# Check connection pool via health endpoint
curl http://localhost:8000/health
```

If pool exhausted:
- Increase `database.pool_size` in config
- Check for connection leaks in logs

---

## ANEL Devices Not Working

1. Verify ANEL Runner is running:
   ```bash
   curl http://localhost:8001/health
   ```

2. Check `ANEL_RUNNER_URL` environment variable

3. Check UDP connectivity from runner to ANEL device

4. Review runner logs for communication errors

---

## Performance Issues

1. **Database pool usage:**
   - Check logs for "pool exhausted" errors
   - Increase `pool_size` if needed

2. **Memory usage:**
   - Check `memory_cleanup` task is running
   - Look for stale cache entries

3. **Slow polling:**
   - Reduce `batch_size` if network congested
   - Increase `device_timeout_seconds` for slow devices
   - Check for offline devices causing timeouts

4. **High CPU:**
   - Check for verification loops
   - Review concurrent operation limits

---

## Verification Stuck

If a device shows "verifying" indefinitely:

1. Check device is actually reachable
2. Look at verification logs for correction attempts
3. Verify success_states config matches device behavior
4. Cancel verification via new command

---

## Protection Blocking Commands

If commands are blocked by protection:

1. Check protection status in device accordion
2. Wait for cooldown to expire
3. Wait for time slice budget to refill
4. Temporarily disable protection via `timeslice_enabled = false`

---

## Satellite Issues

### Satellite won't connect

1. Check network path from satellite to server
2. Verify WebSocket URL is correct
3. Check API key matches

### Commands failing through satellite

1. Check satellite status (online/offline)
2. Verify satellite can reach devices locally
3. Check satellite daemon logs
4. Try removing satellite assignment to test direct connection

---

## Common Error Messages

| Error | Cause | Solution |
|-------|-------|----------|
| "Cooldown active" | Device polled too recently | Wait for cooldown |
| "Not accepting triggers" | Fast-lane blocked | Use web UI or wait for ON |
| "Circuit open" | Job failed 5+ times | Fix issue, then Reset |
| "Budget exhausted" | Protection limit reached | Wait for window reset |
| "Satellite offline" | Satellite disconnected | Check satellite daemon |
| "Pool exhausted" | Too many DB connections | Increase pool_size |
