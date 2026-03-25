# PID Controller Monitor

Dashboard for monitoring PID control loops in real-time.

## Expected Data Format

Comma-separated values with frame delimiters:

```
$setpoint,actual,error,pTerm,iTerm,dTerm,output;
```

| Field | Index | Description | Units |
|-------|-------|-------------|-------|
| Setpoint | 1 | Target value | - |
| Actual | 2 | Measured process variable | - |
| Error | 3 | Setpoint - Actual | - |
| P Term | 4 | Proportional contribution | - |
| I Term | 5 | Integral contribution | - |
| D Term | 6 | Derivative contribution | - |
| Output | 7 | Control output | % |

## Dashboard Widgets

- **Control Loop.** MultiPlot showing setpoint, actual, and error overlaid.
- **PID Terms.** MultiPlot showing P, I, D contributions.
- **Output.** Gauge with ±100% range and ±90% alarm thresholds.
- **Telemetry.** Data grid with setpoint, actual, error, and output.

## Actions

- **Start PID.** Sends `PID_START\r\n`.
- **Stop PID.** Sends `PID_STOP\r\n`.
- **Reset Integral.** Sends `PID_RESET_I\r\n` (clear integral windup).

## Configuration

- Frame delimiters: `$` (start) `;` (end)
- 300 data points per plot for longer time history
- Output alarm at ±90% to catch saturation
