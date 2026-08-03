# Phase 9 — Automation Engine & Scheduler

**Version:** v0.9.0  
**Author:** Lead Software Architect, Principal Backend Engineer, Python Performance Engineer, QA Lead  
**Status:** Released

---

## 1. Architecture Overview

```text
+--------------------------------------------------------------------------------+
|                       AUTOMATION ENGINE ARCHITECTURE                           |
|                                                                                |
|  [ CLI Entry Point (main.py) ]                                                 |
|         │                                                                      |
|         ▼                                                                      |
|  [ AutomationEngine ]                                                          |
|    ├─ start()     ─────── registers and starts SchedulerService daemon loop    |
|    ├─ stop()      ─────── signals stop to SchedulerService                     |
|    ├─ run_once()  ─────── executes single pipeline iteration immediately       |
|    ├─ run_forever() ───── runs scheduler loop blocking forever                 |
|    └─ status()    ─────── returns scheduler state & last run result            |
|         │                                                                      |
|         ▼                                                                      |
|  [ PipelineRunner ]                                                            |
|    1. SearchPlanner.create_search_plan()                                       |
|    2. CollectorManager.execute_plan()                                          |
|    3. ProcessingPipeline.process_batch()                                       |
|    4. RankingEngine.rank_batch()                                               |
|    5. KnowledgeManager.process_opportunity_state()  [skipped in dry-run]      |
|    6. EmailClient.send_daily_digest()               [skipped in dry-run]      |
|    7. PipelineRunner._record_run_history()          [skipped in dry-run]      |
|         │                                                                      |
|         ▼                                                                      |
|  [ SchedulerService ]                                                          |
|    ├─ Background daemon thread (threading.Thread)                              |
|    ├─ ScheduledJob list with interval_seconds triggers                         |
|    └─ YAML-driven configuration (config/scheduler.yaml)                       |
|         │                                                                      |
|         ▼                                                                      |
|  [ LifecyclePublisher → EventBus ]                                             |
|    Publishes run lifecycle events to existing EventBus singleton.              |
|         │                                                                      |
|         ▼                                                                      |
|  [ ShutdownHandler ]                                                           |
|    Registers SIGINT/SIGTERM → cleanup callbacks → clean sys.exit               |
+--------------------------------------------------------------------------------+
```

---

## 2. Sequence Diagram: `--run-once`

```text
  User
   │── python main.py --run-once
   │
   │  [ AutomationEngine.run_once(dry_run=False) ]
   │       │── LifecyclePublisher.publish_event("Collection Started")
   │       │
   │  [ PipelineRunner.run_pipeline() ]
   │       │── SearchPlanner.create_search_plan() → SearchPlan
   │       │── CollectorManager.execute_plan(plan) → CollectorResults
   │       │── ProcessingPipeline.process_batch(items) → processed items
   │       │── RankingEngine.rank_batch(items) → ranked opportunities
   │       │── KnowledgeManager.process_opportunity_state(opp) × N
   │       │── EmailClient.send_daily_digest()
   │       └── _record_run_history() → SearchHistory DB
   │
   │  [ JSON result printed to stdout ]
   └── exit 0
```

---

## 3. Sequence Diagram: `--daemon`

```text
  User
   │── python main.py --daemon
   │
   │  [ AutomationEngine.run_forever() ]
   │       │── start()
   │       │   └── SchedulerService.add_job("Master Pipeline Scan", run_once)
   │       │   └── SchedulerService.start()  [background thread]
   │       │
   │       │── time.sleep(1) loop  ← blocks main thread forever
   │
   │  [ SchedulerService daemon thread ]
   │       └── _run_loop():
   │               While stop_event not set:
   │                   for job in jobs:
   │                       if job.should_run(now): job.execute()
   │                   time.sleep(1)
   │
   │  [ CTRL+C ]
   │       └── ShutdownHandler._handle_signal → callbacks → sys.exit(0)
```

---

## 4. Class Diagram

| Class | Location | Responsibility |
|---|---|---|
| `AutomationEngine` | `engine.py` | Orchestrator — start, stop, run_once, run_forever, status |
| `PipelineRunner` | `pipeline.py` | Executes complete 6-stage search & notify pipeline |
| `SchedulerService` | `scheduler.py` | Background daemon loop firing registered `ScheduledJob`s |
| `ScheduledJob` | `jobs.py` | Individual task descriptor with interval_seconds trigger |
| `LifecyclePublisher` | `lifecycle.py` | Publishes lifecycle events to existing `EventBus` |
| `RunMetrics` | `metrics.py` | Collects per-stage timing measurements |
| `RuntimeState` | `state.py` | Enum: Idle → Running → Sleeping → Stopping → Stopped / Error |
| `ShutdownHandler` | `runtime.py` | Registers SIGINT/SIGTERM and runs cleanup callbacks |

---

## 5. Scheduler Lifecycle

```text
IDLE
  │── start() called
RUNNING
  │── SchedulerService daemon loop active
  │── Periodically: ScheduledJob.should_run() == True
  │── PipelineRunner.run_pipeline() executes
SLEEPING (between runs)
  │── SchedulerService sleeps until next trigger
STOPPING
  │── stop() called / CTRL+C signal
  │── stop_event.set() → thread exits gracefully
STOPPED
  │── Thread joined, DB closed, logs flushed
```

---

## 6. CLI Documentation

| Command | Description |
|---|---|
| `python main.py --run-once` | Runs one full pipeline scan immediately |
| `python main.py --run-once --dry-run` | Runs pipeline with DB writes and email skipped |
| `python main.py --daemon` | Starts daemon loop; keeps scanning per schedule config |
| `python main.py --daemon --dry-run` | Daemon loop; bypasses DB and email |
| `python main.py --scheduler-status` | Displays scheduler state and last run result |
| `python main.py --metrics` | Displays last pipeline execution metrics |
| `python main.py --email-test` | Sends a test HTML email digest |
| `python main.py --health` | Runs full system health diagnostics |
| `python main.py --version` | Displays version, Python, platform info |

---

## 7. Configuration Reference (`config/scheduler.yaml`)

```yaml
enabled: true
mode: daemon              # daemon | run-once
run_on_startup: true

schedule:
  type: daily             # daily | hourly | 6_hours | weekly | custom
  time: "08:00"           # target time for daily/weekly schedules
  timezone: "local"
  interval_seconds: 3600  # for custom/hourly types

retry:
  attempts: 3
  backoff_seconds: 60
```

---

## 8. Failure Recovery Strategy

- **Collector Failures**: Each `CollectorManager.execute_task()` wraps collector errors in try/except with full exception isolation. A failure in `github_collector` does not stop `rss_collector`, `youtube_collector`, or `ctftime_collector`.
- **Processing Failures**: Each item is processed individually. A corrupt item is logged and rejected; valid items continue.
- **Notification Failures**: Email send errors are caught and logged. The pipeline marks `email_sent=False` and continues.
- **DB History Failures**: Run history DB writes are wrapped in a try/except that logs a warning but doesn't abort the pipeline.
