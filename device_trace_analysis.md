# Device Trace Analysis - Request b952270f (07:29:09)
Exhibition ON trigger: 33 devices targeted, 29 successful

## Devices to trace:
1. 192.168.232.149 - PJLink
2. 192.168.232.243 - PJLink (device_id=3925fc80)
3. Atari/Odyssey - NETIO (device_id=26a3e273)
4. FirewatchMonitor - ANEL (device_id=4673b22e)
5. 192.168.233.98 - PJLink (device_id=16cb0057)


## Device 1: 192.168.232.149 (PJLink)

2026-01-30 07:28:29,816 - gallerycontrol.devices.pjlink_manager - INFO - [device=192.168.232.149, host=192.168.232.149, type=pjlink] Getting device state
2026-01-30 07:29:14,794 - gallerycontrol.devices.pjlink_manager - INFO - [req:b952270f] [device=192.168.232.149, host=192.168.232.149, type=pjlink, command=on] Setting device power on
2026-01-30 07:29:50,461 - gallerycontrol.devices.pjlink_manager - INFO - [device=192.168.232.149, host=192.168.232.149, type=pjlink] Getting device state
2026-01-30 07:29:57,465 - gallerycontrol.orchestrator.command_verifier - INFO - [req:b952270f] [device=192.168.232.149, enforcement_duration_seconds=300, device_id=5203144f, direction=ON, type=pjlink] Enforcement task started
2026-01-30 07:29:57,467 - gallerycontrol.orchestrator.command_verifier - INFO - [req:b952270f] [device=192.168.232.149, direction=ON, duration_seconds=300] Active enforcement started
2026-01-30 07:30:04,061 - gallerycontrol.orchestrator.command_verifier - INFO - [req:560082a8] [device=192.168.232.149, device_id=5203144f, direction=ON] Cancelling active verification
2026-01-30 07:30:04,061 - gallerycontrol.orchestrator.command_verifier - INFO - [req:b952270f] [device=192.168.232.149, direction=ON] Verification cancelled
2026-01-30 07:30:04,061 - gallerycontrol.orchestrator.command_orchestrator - INFO - [req:560082a8] [device=192.168.232.149, new_command=on, source=web] Cancelled active verification for new command
2026-01-30 07:30:08,404 - gallerycontrol.monitoring.state_monitor - WARNING - [device=192.168.232.149, host=192.168.232.149, error=Cooldown active, next allowed at 2026-01-30 07:30:20.526745+00:00 (12.1s remaining)] Failed to get device state
2026-01-30 07:31:19,306 - gallerycontrol.devices.pjlink_manager - INFO - [device=192.168.232.149, host=192.168.232.149, type=pjlink] Getting device state
2026-01-30 07:32:41,314 - gallerycontrol.devices.pjlink_manager - INFO - [device=192.168.232.149, host=192.168.232.149, type=pjlink] Getting device state
2026-01-30 07:33:29,222 - gallerycontrol.devices.pjlink_manager - INFO - [device=192.168.232.149, host=192.168.232.149, info={'name': 'M402 Series', 'manufacturer': 'NEC', 'product': 'M402_Series', 'lamps': [{'hours': 3565, 'on': True}], 'lamp_hours': 3565, 'lamp_on': True, 'errors': {'fan': 0, 'lamp': 0, 'temperature': 0, 'cover': 0, 'filter': 0, 'other': 0}, 'has_errors': False, 'has_warnings': False, 'class': '1'}] Retrieved device info
2026-01-30 07:33:29,222 - gallerycontrol.services.asset_service - INFO - [device=192.168.232.149, asset_id=56f48397, lamp_hours=3565, event_type=power_off] Recorded lamp hours
2026-01-30 07:34:01,595 - gallerycontrol.devices.pjlink_manager - INFO - [device=192.168.232.149, host=192.168.232.149, type=pjlink] Getting device state
2026-01-30 07:35:21,420 - gallerycontrol.devices.pjlink_manager - INFO - [device=192.168.232.149, host=192.168.232.149, type=pjlink] Getting device state

## Device 2: 192.168.232.243 (PJLink, device_id=3925fc80)

2026-01-30 07:07:31,244 - gallerycontrol.devices.pjlink_manager - INFO - [device=192.168.232.243, host=192.168.232.243, type=pjlink] Getting device state
2026-01-30 07:25:58,912 - gallerycontrol.scheduler.cron_scheduler - INFO - [req:4fe22337] [name=lamp_hours:3925fc80-d8f9-4c5c-983a-72e675adbf04, job_type=system, run_at=2026-01-30T07:32:58.911149, target_type=device] Scheduled one-shot job
2026-01-30 07:28:13,569 - gallerycontrol.devices.pjlink_manager - INFO - [device=192.168.232.243, host=192.168.232.243, type=pjlink] Getting device state
2026-01-30 07:28:13,657 - gallerycontrol.monitoring.state_monitor - INFO - [device=192.168.232.243, state=0, target_states=[0, 2]] Device reached target state
2026-01-30 07:28:13,657 - gallerycontrol.orchestrator.command_verifier - INFO - [device=192.168.232.243, state=0, enforcement_remaining_seconds=170, corrections_sent=0] State OK during enforcement
2026-01-30 07:28:47,886 - gallerycontrol.devices.pjlink_manager - INFO - [device=192.168.232.243, host=192.168.232.243, type=pjlink] Getting device state
2026-01-30 07:28:47,960 - gallerycontrol.monitoring.state_monitor - INFO - [device=192.168.232.243, state=0, target_states=[0, 2]] Device reached target state
2026-01-30 07:28:47,961 - gallerycontrol.orchestrator.command_verifier - INFO - [device=192.168.232.243, state=0, enforcement_remaining_seconds=136, corrections_sent=0] State OK during enforcement
2026-01-30 07:29:09,863 - gallerycontrol.orchestrator.command_verifier - INFO - [req:b952270f] [device=192.168.232.243, device_id=3925fc80, direction=OFF] Cancelling active verification
2026-01-30 07:29:09,863 - gallerycontrol.monitoring.state_monitor - INFO - [req:b952270f] [device_id=3925fc80] Device unregistered from fast polling
2026-01-30 07:29:09,863 - gallerycontrol.orchestrator.command_verifier - INFO - [req:4fe22337] [device=192.168.232.243, direction=OFF] Verification cancelled
2026-01-30 07:29:09,863 - gallerycontrol.orchestrator.command_orchestrator - INFO - [req:b952270f] [device=192.168.232.243, new_command=on, source=web] Cancelled active verification for new command
2026-01-30 07:29:55,738 - gallerycontrol.devices.pjlink_manager - INFO - [device=192.168.232.243, host=192.168.232.243, type=pjlink] Getting device state
2026-01-30 07:30:24,546 - gallerycontrol.devices.pjlink_manager - INFO - [device=192.168.232.243, host=192.168.232.243, info={'name': 'M402 Series', 'manufacturer': 'NEC', 'product': 'M402_Series', 'lamps': [{'hours': 2325, 'on': False}], 'lamp_hours': 2325, 'lamp_on': False, 'errors': {'fan': 0, 'lamp': 0, 'temperature': 0, 'cover': 0, 'filter': 0, 'other': 0}, 'has_errors': False, 'has_warnings': False, 'class': '1'}] Retrieved device info
2026-01-30 07:31:07,164 - gallerycontrol.devices.pjlink_manager - INFO - [device=192.168.232.243, host=192.168.232.243, type=pjlink] Getting device state
2026-01-30 07:32:23,714 - gallerycontrol.devices.pjlink_manager - INFO - [device=192.168.232.243, host=192.168.232.243, type=pjlink] Getting device state
2026-01-30 07:33:29,559 - gallerycontrol.scheduler.cron_scheduler - INFO - [job=lamp_hours:3925fc80-d8f9-4c5c-983a-72e675adbf04, job_type=system, task_name=lamp_hours_record] Executing scheduled job
2026-01-30 07:33:30,238 - gallerycontrol.devices.pjlink_manager - INFO - [device=192.168.232.243, host=192.168.232.243, info={'name': 'M402 Series', 'manufacturer': 'NEC', 'product': 'M402_Series', 'lamps': [{'hours': 2325, 'on': False}], 'lamp_hours': 2325, 'lamp_on': False, 'errors': {'fan': 0, 'lamp': 0, 'temperature': 0, 'cover': 0, 'filter': 0, 'other': 0}, 'has_errors': False, 'has_warnings': False, 'class': '1'}] Retrieved device info
2026-01-30 07:33:30,238 - gallerycontrol.services.asset_service - INFO - [device=192.168.232.243, asset_id=a5cb0e0d, lamp_hours=2325, event_type=power_off] Recorded lamp hours
2026-01-30 07:33:30,268 - gallerycontrol.scheduler.cron_scheduler - INFO - [job=lamp_hours:3925fc80-d8f9-4c5c-983a-72e675adbf04, duration_ms=700] Job completed successfully
2026-01-30 07:33:43,905 - gallerycontrol.devices.pjlink_manager - INFO - [device=192.168.232.243, host=192.168.232.243, type=pjlink] Getting device state
2026-01-30 07:35:03,832 - gallerycontrol.devices.pjlink_manager - INFO - [device=192.168.232.243, host=192.168.232.243, type=pjlink] Getting device state

## Device 3: Atari/Odyssey (NETIO, device_id=26a3e273)

2026-01-30 07:28:02,054 - gallerycontrol.monitoring.state_monitor - INFO - [device=Atari/Odyssey, state=0, target_states=[0]] Device reached target state
2026-01-30 07:28:02,054 - gallerycontrol.orchestrator.command_verifier - INFO - [device=Atari/Odyssey, state=0, enforcement_remaining_seconds=181, corrections_sent=0] State OK during enforcement
2026-01-30 07:28:53,914 - gallerycontrol.monitoring.state_monitor - INFO - [device=Atari/Odyssey, state=0, target_states=[0]] Device reached target state
2026-01-30 07:28:53,915 - gallerycontrol.orchestrator.command_verifier - INFO - [device=Atari/Odyssey, state=0, enforcement_remaining_seconds=130, corrections_sent=0] State OK during enforcement
2026-01-30 07:29:09,863 - gallerycontrol.orchestrator.command_verifier - INFO - [req:b952270f] [device=Atari/Odyssey, device_id=26a3e273, direction=OFF] Cancelling active verification
2026-01-30 07:29:09,863 - gallerycontrol.monitoring.state_monitor - INFO - [req:b952270f] [device_id=26a3e273] Device unregistered from fast polling
2026-01-30 07:29:09,863 - gallerycontrol.orchestrator.command_verifier - INFO - [req:4fe22337] [device=Atari/Odyssey, direction=OFF] Verification cancelled
2026-01-30 07:29:09,863 - gallerycontrol.orchestrator.command_orchestrator - INFO - [req:b952270f] [device=Atari/Odyssey, new_command=on, source=web] Cancelled active verification for new command
2026-01-30 07:29:20,612 - gallerycontrol.database.state_logger - INFO - [req:b952270f] [device_id=26a3e273, previous_state=0, new_state=1, trigger=command] Device state changed
2026-01-30 07:29:57,465 - gallerycontrol.orchestrator.command_verifier - INFO - [req:b952270f] [device=Atari/Odyssey, enforcement_duration_seconds=300, device_id=26a3e273, direction=ON, type=netio] Enforcement task started
2026-01-30 07:29:57,467 - gallerycontrol.orchestrator.command_verifier - INFO - [req:b952270f] [device=Atari/Odyssey, direction=ON, duration_seconds=300] Active enforcement started
2026-01-30 07:29:57,467 - gallerycontrol.monitoring.state_monitor - INFO - [req:b952270f] [device_id=26a3e273, target_states=[1]] Device registered for fast polling
2026-01-30 07:30:04,062 - gallerycontrol.orchestrator.command_verifier - INFO - [req:560082a8] [device=Atari/Odyssey, device_id=26a3e273, direction=ON] Cancelling active verification
2026-01-30 07:30:04,062 - gallerycontrol.monitoring.state_monitor - INFO - [req:560082a8] [device_id=26a3e273] Device unregistered from fast polling
2026-01-30 07:30:04,062 - gallerycontrol.orchestrator.command_verifier - INFO - [req:b952270f] [device=Atari/Odyssey, direction=ON] Verification cancelled
2026-01-30 07:30:04,062 - gallerycontrol.orchestrator.command_orchestrator - INFO - [req:560082a8] [device=Atari/Odyssey, new_command=on, source=web] Cancelled active verification for new command
2026-01-30 07:30:14,170 - gallerycontrol.monitoring.state_monitor - WARNING - [device=Atari/Odyssey, host=netzwerksteckdose-netio-013.zkm.de, error=Cooldown active, next allowed at 2026-01-30 07:30:18.821536+00:00 (4.7s remaining)] Failed to get device state
2026-01-30 07:30:14,174 - gallerycontrol.database.state_logger - INFO - [device_id=26a3e273, previous_state=1, new_state=-1, trigger=polling] Device state changed
2026-01-30 07:30:51,515 - gallerycontrol.orchestrator.command_verifier - INFO - [req:560082a8] [device=Atari/Odyssey, enforcement_duration_seconds=300, device_id=26a3e273, direction=ON, type=netio] Enforcement task started
2026-01-30 07:30:51,516 - gallerycontrol.orchestrator.command_verifier - INFO - [req:560082a8] [device=Atari/Odyssey, direction=ON, duration_seconds=300] Active enforcement started
2026-01-30 07:30:51,516 - gallerycontrol.monitoring.state_monitor - INFO - [req:560082a8] [device_id=26a3e273, target_states=[1]] Device registered for fast polling
2026-01-30 07:31:07,469 - gallerycontrol.database.state_logger - INFO - [device_id=26a3e273, previous_state=-1, new_state=1, trigger=polling] Device state changed
2026-01-30 07:31:07,476 - gallerycontrol.monitoring.state_monitor - INFO - [device=Atari/Odyssey, state=1, target_states=[1]] Device reached target state
2026-01-30 07:31:07,476 - gallerycontrol.orchestrator.command_verifier - INFO - [device=Atari/Odyssey, state=1, enforcement_remaining_seconds=284, corrections_sent=0] State OK during enforcement
2026-01-30 07:31:44,426 - gallerycontrol.monitoring.state_monitor - INFO - [device=Atari/Odyssey, state=1, target_states=[1]] Device reached target state
2026-01-30 07:31:44,426 - gallerycontrol.orchestrator.command_verifier - INFO - [device=Atari/Odyssey, state=1, enforcement_remaining_seconds=247, corrections_sent=0] State OK during enforcement
2026-01-30 07:32:24,003 - gallerycontrol.monitoring.state_monitor - INFO - [device=Atari/Odyssey, state=1, target_states=[1]] Device reached target state
2026-01-30 07:32:24,003 - gallerycontrol.orchestrator.command_verifier - INFO - [device=Atari/Odyssey, state=1, enforcement_remaining_seconds=207, corrections_sent=0] State OK during enforcement
2026-01-30 07:33:05,156 - gallerycontrol.monitoring.state_monitor - INFO - [device=Atari/Odyssey, state=1, target_states=[1]] Device reached target state
2026-01-30 07:33:05,156 - gallerycontrol.orchestrator.command_verifier - INFO - [device=Atari/Odyssey, state=1, enforcement_remaining_seconds=166, corrections_sent=0] State OK during enforcement
2026-01-30 07:33:44,145 - gallerycontrol.monitoring.state_monitor - INFO - [device=Atari/Odyssey, state=1, target_states=[1]] Device reached target state
2026-01-30 07:33:44,146 - gallerycontrol.orchestrator.command_verifier - INFO - [device=Atari/Odyssey, state=1, enforcement_remaining_seconds=127, corrections_sent=0] State OK during enforcement
2026-01-30 07:34:25,229 - gallerycontrol.monitoring.state_monitor - INFO - [device=Atari/Odyssey, state=1, target_states=[1]] Device reached target state
2026-01-30 07:34:25,229 - gallerycontrol.orchestrator.command_verifier - INFO - [device=Atari/Odyssey, state=1, enforcement_remaining_seconds=86, corrections_sent=0] State OK during enforcement
2026-01-30 07:35:04,089 - gallerycontrol.monitoring.state_monitor - INFO - [device=Atari/Odyssey, state=1, target_states=[1]] Device reached target state
2026-01-30 07:35:04,089 - gallerycontrol.orchestrator.command_verifier - INFO - [device=Atari/Odyssey, state=1, enforcement_remaining_seconds=47, corrections_sent=0] State OK during enforcement
2026-01-30 07:35:46,781 - gallerycontrol.monitoring.state_monitor - INFO - [device=Atari/Odyssey, state=1, target_states=[1]] Device reached target state
2026-01-30 07:35:46,781 - gallerycontrol.orchestrator.command_verifier - INFO - [device=Atari/Odyssey, state=1, enforcement_remaining_seconds=4, corrections_sent=0] State OK during enforcement
2026-01-30 07:35:51,522 - gallerycontrol.monitoring.state_monitor - INFO - [req:560082a8] [device_id=26a3e273] Device unregistered from fast polling
2026-01-30 07:35:51,522 - gallerycontrol.orchestrator.command_verifier - WARNING - [req:560082a8] [device=Atari/Odyssey, direction=ON, error=Cooldown active, next allowed at 2026-01-30 07:35:51.745530+00:00 (0.2s remaining)] Device offline at end of enforcement period - skipping

## Device 4: FirewatchMonitor (ANEL, device_id=4673b22e)

2026-01-30 07:28:29,933 - gallerycontrol.monitoring.state_monitor - INFO - [device=FirewatchMonitor, state=0, target_states=[0]] Device reached target state
2026-01-30 07:28:29,933 - gallerycontrol.orchestrator.command_verifier - INFO - [device=FirewatchMonitor, state=0, enforcement_remaining_seconds=154, corrections_sent=0] State OK during enforcement
2026-01-30 07:29:09,865 - gallerycontrol.orchestrator.command_verifier - INFO - [req:b952270f] [device=FirewatchMonitor, device_id=4673b22e, direction=OFF] Cancelling active verification
2026-01-30 07:29:09,865 - gallerycontrol.monitoring.state_monitor - INFO - [req:b952270f] [device_id=4673b22e] Device unregistered from fast polling
2026-01-30 07:29:09,865 - gallerycontrol.orchestrator.command_verifier - INFO - [req:4fe22337] [device=FirewatchMonitor, direction=OFF] Verification cancelled
2026-01-30 07:29:09,865 - gallerycontrol.orchestrator.command_orchestrator - INFO - [req:b952270f] [device=FirewatchMonitor, new_command=on, source=web] Cancelled active verification for new command
2026-01-30 07:29:39,608 - gallerycontrol.database.state_logger - INFO - [req:b952270f] [device_id=4673b22e, previous_state=0, new_state=1, trigger=command] Device state changed
2026-01-30 07:29:57,466 - gallerycontrol.orchestrator.command_verifier - INFO - [req:b952270f] [device=FirewatchMonitor, enforcement_duration_seconds=300, device_id=4673b22e, direction=ON, type=anel] Enforcement task started
2026-01-30 07:29:57,468 - gallerycontrol.orchestrator.command_verifier - INFO - [req:b952270f] [device=FirewatchMonitor, direction=ON, duration_seconds=300] Active enforcement started
2026-01-30 07:29:57,468 - gallerycontrol.monitoring.state_monitor - INFO - [req:b952270f] [device_id=4673b22e, target_states=[1]] Device registered for fast polling
2026-01-30 07:30:04,064 - gallerycontrol.orchestrator.command_verifier - INFO - [req:560082a8] [device=FirewatchMonitor, device_id=4673b22e, direction=ON] Cancelling active verification
2026-01-30 07:30:04,064 - gallerycontrol.monitoring.state_monitor - INFO - [req:560082a8] [device_id=4673b22e] Device unregistered from fast polling
2026-01-30 07:30:04,064 - gallerycontrol.orchestrator.command_verifier - INFO - [req:b952270f] [device=FirewatchMonitor, direction=ON] Verification cancelled
2026-01-30 07:30:04,064 - gallerycontrol.orchestrator.command_orchestrator - INFO - [req:560082a8] [device=FirewatchMonitor, new_command=on, source=web] Cancelled active verification for new command
2026-01-30 07:30:51,516 - gallerycontrol.orchestrator.command_verifier - INFO - [req:560082a8] [device=FirewatchMonitor, enforcement_duration_seconds=300, device_id=4673b22e, direction=ON, type=anel] Enforcement task started
2026-01-30 07:30:51,517 - gallerycontrol.orchestrator.command_verifier - INFO - [req:560082a8] [device=FirewatchMonitor, direction=ON, duration_seconds=300] Active enforcement started
2026-01-30 07:30:51,517 - gallerycontrol.monitoring.state_monitor - INFO - [req:560082a8] [device_id=4673b22e, target_states=[1]] Device registered for fast polling
2026-01-30 07:31:14,117 - gallerycontrol.monitoring.state_monitor - INFO - [device=FirewatchMonitor, state=1, target_states=[1]] Device reached target state
2026-01-30 07:31:14,118 - gallerycontrol.orchestrator.command_verifier - INFO - [device=FirewatchMonitor, state=1, enforcement_remaining_seconds=277, corrections_sent=0] State OK during enforcement
2026-01-30 07:32:13,041 - gallerycontrol.monitoring.state_monitor - INFO - [device=FirewatchMonitor, state=1, target_states=[1]] Device reached target state
2026-01-30 07:32:13,041 - gallerycontrol.orchestrator.command_verifier - INFO - [device=FirewatchMonitor, state=1, enforcement_remaining_seconds=218, corrections_sent=0] State OK during enforcement
2026-01-30 07:33:10,249 - gallerycontrol.monitoring.state_monitor - INFO - [device=FirewatchMonitor, state=1, target_states=[1]] Device reached target state
2026-01-30 07:33:10,249 - gallerycontrol.orchestrator.command_verifier - INFO - [device=FirewatchMonitor, state=1, enforcement_remaining_seconds=161, corrections_sent=0] State OK during enforcement
2026-01-30 07:34:02,897 - gallerycontrol.monitoring.state_monitor - INFO - [device=FirewatchMonitor, state=1, target_states=[1]] Device reached target state
2026-01-30 07:34:02,897 - gallerycontrol.orchestrator.command_verifier - INFO - [device=FirewatchMonitor, state=1, enforcement_remaining_seconds=108, corrections_sent=0] State OK during enforcement
2026-01-30 07:34:52,964 - gallerycontrol.monitoring.state_monitor - INFO - [device=FirewatchMonitor, state=1, target_states=[1]] Device reached target state
2026-01-30 07:34:52,964 - gallerycontrol.orchestrator.command_verifier - INFO - [device=FirewatchMonitor, state=1, enforcement_remaining_seconds=58, corrections_sent=0] State OK during enforcement
2026-01-30 07:35:47,070 - gallerycontrol.monitoring.state_monitor - INFO - [device=FirewatchMonitor, state=1, target_states=[1]] Device reached target state
2026-01-30 07:35:47,070 - gallerycontrol.orchestrator.command_verifier - INFO - [device=FirewatchMonitor, state=1, enforcement_remaining_seconds=4, corrections_sent=0] State OK during enforcement
2026-01-30 07:35:51,525 - gallerycontrol.monitoring.state_monitor - INFO - [req:560082a8] [device_id=4673b22e] Device unregistered from fast polling
2026-01-30 07:35:56,533 - gallerycontrol.orchestrator.command_verifier - WARNING - [req:560082a8] [device=FirewatchMonitor, direction=ON, error=] Device offline at end of enforcement period - skipping

## Device 5: 192.168.233.98 (PJLink, device_id=16cb0057)

2026-01-30 07:25:58,913 - gallerycontrol.scheduler.cron_scheduler - INFO - [req:4fe22337] [name=lamp_hours:16cb0057-a10d-4707-8840-552bef9c6295, job_type=system, run_at=2026-01-30T07:32:58.910845, target_type=device] Scheduled one-shot job
2026-01-30 07:28:35,061 - gallerycontrol.devices.pjlink_manager - INFO - [device=192.168.233.98, host=192.168.233.98, type=pjlink] Getting device state
2026-01-30 07:28:35,104 - gallerycontrol.monitoring.state_monitor - INFO - [device=192.168.233.98, state=0, target_states=[0, 2]] Device reached target state
2026-01-30 07:28:35,104 - gallerycontrol.orchestrator.command_verifier - INFO - [device=192.168.233.98, state=0, enforcement_remaining_seconds=148, corrections_sent=0] State OK during enforcement
2026-01-30 07:29:09,865 - gallerycontrol.orchestrator.command_verifier - INFO - [req:b952270f] [device=192.168.233.98, device_id=16cb0057, direction=OFF] Cancelling active verification
2026-01-30 07:29:09,865 - gallerycontrol.monitoring.state_monitor - INFO - [req:b952270f] [device_id=16cb0057] Device unregistered from fast polling
2026-01-30 07:29:09,866 - gallerycontrol.orchestrator.command_verifier - INFO - [req:4fe22337] [device=192.168.233.98, direction=OFF] Verification cancelled
2026-01-30 07:29:09,866 - gallerycontrol.orchestrator.command_orchestrator - INFO - [req:b952270f] [device=192.168.233.98, new_command=on, source=web] Cancelled active verification for new command
2026-01-30 07:29:49,850 - gallerycontrol.devices.pjlink_manager - INFO - [req:b952270f] [device=192.168.233.98, host=192.168.233.98, type=pjlink, command=on] Setting device power on
2026-01-30 07:29:49,870 - gallerycontrol.database.state_logger - INFO - [req:b952270f] [device_id=16cb0057, previous_state=0, new_state=3, trigger=command] Device state changed
2026-01-30 07:29:50,932 - gallerycontrol.monitoring.state_monitor - WARNING - [device=192.168.233.98, host=192.168.233.98, error=Cooldown active, next allowed at 2026-01-30 07:30:19.868043+00:00 (28.9s remaining)] Failed to get device state
2026-01-30 07:29:50,934 - gallerycontrol.database.state_logger - INFO - [device_id=16cb0057, previous_state=3, new_state=-1, trigger=polling] Device state changed
2026-01-30 07:29:57,466 - gallerycontrol.orchestrator.command_verifier - INFO - [req:b952270f] [device=192.168.233.98, enforcement_duration_seconds=300, device_id=16cb0057, direction=ON, type=pjlink] Enforcement task started
2026-01-30 07:29:57,468 - gallerycontrol.orchestrator.command_verifier - INFO - [req:b952270f] [device=192.168.233.98, direction=ON, duration_seconds=300] Active enforcement started
2026-01-30 07:29:57,468 - gallerycontrol.monitoring.state_monitor - INFO - [req:b952270f] [device_id=16cb0057, target_states=[1, 3]] Device registered for fast polling
2026-01-30 07:30:04,065 - gallerycontrol.orchestrator.command_verifier - INFO - [req:560082a8] [device=192.168.233.98, device_id=16cb0057, direction=ON] Cancelling active verification
2026-01-30 07:30:04,065 - gallerycontrol.monitoring.state_monitor - INFO - [req:560082a8] [device_id=16cb0057] Device unregistered from fast polling
2026-01-30 07:30:04,065 - gallerycontrol.orchestrator.command_verifier - INFO - [req:b952270f] [device=192.168.233.98, direction=ON] Verification cancelled
2026-01-30 07:30:04,065 - gallerycontrol.orchestrator.command_orchestrator - INFO - [req:560082a8] [device=192.168.233.98, new_command=on, source=web] Cancelled active verification for new command
2026-01-30 07:30:19,273 - gallerycontrol.monitoring.state_monitor - WARNING - [device=192.168.233.98, host=192.168.233.98, error=Cooldown active, next allowed at 2026-01-30 07:30:19.868043+00:00 (0.6s remaining)] Failed to get device state
2026-01-30 07:30:41,433 - gallerycontrol.devices.pjlink_manager - INFO - [req:560082a8] [device=192.168.233.98, host=192.168.233.98, type=pjlink, command=on] Setting device power on
2026-01-30 07:30:41,459 - gallerycontrol.database.state_logger - INFO - [req:560082a8] [device_id=16cb0057, previous_state=-1, new_state=3, trigger=command] Device state changed
2026-01-30 07:30:51,516 - gallerycontrol.orchestrator.command_verifier - INFO - [req:560082a8] [device=192.168.233.98, enforcement_duration_seconds=300, device_id=16cb0057, direction=ON, type=pjlink] Enforcement task started
2026-01-30 07:30:51,517 - gallerycontrol.orchestrator.command_verifier - INFO - [req:560082a8] [device=192.168.233.98, direction=ON, duration_seconds=300] Active enforcement started
2026-01-30 07:30:51,517 - gallerycontrol.monitoring.state_monitor - INFO - [req:560082a8] [device_id=16cb0057, target_states=[1, 3]] Device registered for fast polling
2026-01-30 07:31:00,479 - gallerycontrol.monitoring.state_monitor - WARNING - [device=192.168.233.98, host=192.168.233.98, error=Cooldown active, next allowed at 2026-01-30 07:31:11.457126+00:00 (11.2s remaining)] Device offline during enforcement - skipping
2026-01-30 07:31:49,742 - gallerycontrol.devices.pjlink_manager - INFO - [device=192.168.233.98, host=192.168.233.98, type=pjlink] Getting device state
2026-01-30 07:31:49,795 - gallerycontrol.database.state_logger - INFO - [device_id=16cb0057, previous_state=3, new_state=1, trigger=polling] Device state changed
2026-01-30 07:31:49,803 - gallerycontrol.monitoring.state_monitor - INFO - [device=192.168.233.98, state=1, target_states=[1, 3]] Device reached target state
2026-01-30 07:31:49,803 - gallerycontrol.orchestrator.command_verifier - INFO - [device=192.168.233.98, state=1, enforcement_remaining_seconds=241, corrections_sent=0] State OK during enforcement
2026-01-30 07:32:47,803 - gallerycontrol.devices.pjlink_manager - INFO - [device=192.168.233.98, host=192.168.233.98, type=pjlink] Getting device state
2026-01-30 07:32:47,859 - gallerycontrol.monitoring.state_monitor - INFO - [device=192.168.233.98, state=1, target_states=[1, 3]] Device reached target state
2026-01-30 07:32:47,859 - gallerycontrol.orchestrator.command_verifier - INFO - [device=192.168.233.98, state=1, enforcement_remaining_seconds=183, corrections_sent=0] State OK during enforcement
2026-01-30 07:33:30,268 - gallerycontrol.scheduler.cron_scheduler - INFO - [job=lamp_hours:16cb0057-a10d-4707-8840-552bef9c6295, job_type=system, task_name=lamp_hours_record] Executing scheduled job
2026-01-30 07:33:30,387 - gallerycontrol.devices.pjlink_manager - INFO - [device=192.168.233.98, host=192.168.233.98, info={'name': 'PJ-2340006RA', 'manufacturer': 'NEC Display Solutions, Ltd.', 'product': 'P554 Series', 'lamps': [{'hours': 683, 'on': True}], 'lamp_hours': 683, 'lamp_on': True, 'errors': {'fan': 0, 'lamp': 0, 'temperature': 0, 'cover': 0, 'filter': 0, 'other': 0}, 'has_errors': False, 'has_warnings': False, 'class': '1'}] Retrieved device info
2026-01-30 07:33:30,388 - gallerycontrol.services.asset_service - INFO - [device=192.168.233.98, asset_id=6fc3d6b4, lamp_hours=683, event_type=power_off] Recorded lamp hours
2026-01-30 07:33:30,403 - gallerycontrol.scheduler.cron_scheduler - INFO - [job=lamp_hours:16cb0057-a10d-4707-8840-552bef9c6295, duration_ms=128] Job completed successfully
2026-01-30 07:33:32,881 - gallerycontrol.devices.pjlink_manager - INFO - [device=192.168.233.98, host=192.168.233.98, type=pjlink] Getting device state
2026-01-30 07:33:32,923 - gallerycontrol.monitoring.state_monitor - INFO - [device=192.168.233.98, state=1, target_states=[1, 3]] Device reached target state
2026-01-30 07:33:32,923 - gallerycontrol.orchestrator.command_verifier - INFO - [device=192.168.233.98, state=1, enforcement_remaining_seconds=138, corrections_sent=0] State OK during enforcement
2026-01-30 07:34:30,997 - gallerycontrol.devices.pjlink_manager - INFO - [device=192.168.233.98, host=192.168.233.98, type=pjlink] Getting device state
2026-01-30 07:34:31,064 - gallerycontrol.monitoring.state_monitor - INFO - [device=192.168.233.98, state=1, target_states=[1, 3]] Device reached target state
2026-01-30 07:34:31,064 - gallerycontrol.orchestrator.command_verifier - INFO - [device=192.168.233.98, state=1, enforcement_remaining_seconds=80, corrections_sent=0] State OK during enforcement
2026-01-30 07:35:27,782 - gallerycontrol.devices.pjlink_manager - INFO - [device=192.168.233.98, host=192.168.233.98, type=pjlink] Getting device state
2026-01-30 07:35:27,841 - gallerycontrol.monitoring.state_monitor - INFO - [device=192.168.233.98, state=1, target_states=[1, 3]] Device reached target state
2026-01-30 07:35:27,841 - gallerycontrol.orchestrator.command_verifier - INFO - [device=192.168.233.98, state=1, enforcement_remaining_seconds=23, corrections_sent=0] State OK during enforcement
2026-01-30 07:35:51,525 - gallerycontrol.monitoring.state_monitor - INFO - [req:560082a8] [device_id=16cb0057] Device unregistered from fast polling
2026-01-30 07:35:51,525 - gallerycontrol.orchestrator.command_verifier - WARNING - [req:560082a8] [device=192.168.233.98, direction=ON, error=Cooldown active, next allowed at 2026-01-30 07:35:57.817642+00:00 (6.3s remaining)] Device offline at end of enforcement period - skipping

---

# ANALYSIS

## Device 1: 192.168.232.149 (PJLink) - ✅ SUCCESS
- 07:29:14 - **Received ON command** ✓
- 07:29:57 - Enforcement started
- 07:30:04 - Verification cancelled by SECOND ON trigger (req:560082a8)
- 07:33:29 - lamp_on: **True** ✓

## Device 2: 192.168.232.243 (PJLink) - ❌ FAILED - NO ON COMMAND SENT!
- 07:29:09 - Verification cancelled, new_command=on (preparation)
- 07:29:55 - Next log is "Getting device state" - NO "Setting power on"!
- 07:30:24 - lamp_on: **False** - device stayed OFF
- **CRITICAL: This device was in the 33 targeted but NEVER received the power ON command!**

## Device 3: Atari/Odyssey (NETIO) - ✅ SUCCESS
- 07:29:20 - **state changed 0→1 via command** ✓
- 07:30:14 - Cooldown blocked poll, state briefly -1
- 07:31:07 - Recovered to state=1 via polling

## Device 4: FirewatchMonitor (ANEL) - ✅ SUCCESS
- 07:29:39 - **state changed 0→1 via command** ✓
- 07:31:14+ - State=1, "State OK during enforcement"

## Device 5: 192.168.233.98 (PJLink) - ✅ SUCCESS
- 07:29:49 - **Received ON command** ✓
- 07:29:50 - Cooldown blocked poll, state set to -1
- 07:30:41 - Second ON command from new trigger
- 07:31:49 - Final state=1 (ON)

---

# ROOT CAUSE IDENTIFIED

**Device 192.168.232.243 was NEVER sent an ON command!**

Looking at the PJLink ON commands in request b952270f:
```
07:29:14 - 192.168.232.149
07:29:27 - 192.168.232.26
07:29:29 - 192.168.232.69
07:29:40 - 192.168.232.228
07:29:41 - 192.168.233.95
07:29:42 - 192.168.233.97
07:29:43 - 192.168.232.130
07:29:49 - 192.168.233.98
07:29:54 - 192.168.232.160
07:29:55 - 192.168.232.215
```

That's only 10 PJLink commands for a 33-device exhibition.
192.168.232.243 is NOT in this list!

This is NOT a cooldown bug - the device was targeted but the ON command was never sent.

Possible causes:
1. Cooldown check on set_power() BEFORE sending command
2. Device already in "on" state (skipped)?
3. Silent failure in the stagger loop
4. Manager returning early without sending command

The cooldown on get_state() is a separate issue - it causes temporary state=-1 during polls,
but devices that receive commands DO eventually turn on correctly.


---

# ROOT CAUSE CONFIRMED!

## Timeline for device 192.168.232.243:

```
07:25:58 - OFF command sent -> cooldown set, expires 07:26:28
07:26:52 - get_state SUCCESS -> cooldown RESET, expires 07:27:22
07:27:23 - get_state SUCCESS -> cooldown RESET, expires 07:27:53
07:28:13 - get_state SUCCESS -> cooldown RESET, expires 07:28:43
07:28:47 - get_state SUCCESS -> cooldown RESET, expires 07:29:17
07:29:09 - ON command attempted -> BLOCKED (8 seconds remaining!)
```

**The get_state() polling is resetting the cooldown every 30 seconds!**

In the OLD code (v1.2.0 deployed), BOTH get_state and set_power record cooldowns:
```python
async def get_state(self, device) -> DeviceResult:
    ...
    # Record successful request
    cooldown = self.config.get("cooldown_seconds", 30)
    self.cooldown_manager.record_request(device.id, cooldown)  # BUG!
```

This means:
1. State polling every ~30 seconds keeps resetting the cooldown
2. When an ON/OFF command tries to execute, it may be blocked if polling happened recently
3. The command silently returns a cooldown error without any log

## Why this is intermittent:
- If poll happens at T, cooldown expires at T+30
- If command comes at T+35, it works
- If command comes at T+25, it's BLOCKED with no log

## The fix we made (v1.2.3, NOT DEPLOYED):
- Removed cooldown from get_state() in all managers
- Only set_power() records cooldowns

## Current status:
- Deployed: v1.2.0 (has bug)
- Fixed: v1.2.3 (ready to deploy)


---

# ROOT CAUSE CONFIRMED!

## Timeline for device 192.168.232.243:

```
07:25:58 - OFF command sent -> cooldown set, expires 07:26:28
07:26:52 - get_state SUCCESS -> cooldown RESET, expires 07:27:22
07:27:23 - get_state SUCCESS -> cooldown RESET, expires 07:27:53
07:28:13 - get_state SUCCESS -> cooldown RESET, expires 07:28:43
07:28:47 - get_state SUCCESS -> cooldown RESET, expires 07:29:17
07:29:09 - ON command attempted -> BLOCKED (8 seconds remaining!)
```

**The get_state() polling is resetting the cooldown every 30 seconds!**

In the OLD code (v1.2.0 deployed), BOTH get_state and set_power record cooldowns.
This means:
1. State polling every ~30 seconds keeps resetting the cooldown
2. When an ON/OFF command tries to execute, it may be blocked if polling happened recently
3. The command silently returns a cooldown error without any log

## Why this is intermittent:
- If poll happens at T, cooldown expires at T+30
- If command comes at T+35, it works
- If command comes at T+25, it's BLOCKED with no log

## The fix we made (v1.2.3, NOT DEPLOYED):
- Removed cooldown from get_state() in all managers
- Only set_power() records cooldowns

## Current status:
- Deployed: v1.2.0 (has bug)
- Fixed: v1.2.3 (committed, ready to deploy)
