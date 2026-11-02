---
name: edit-plan
description: Lay out a numbered plan with a time estimate for every step before any editing work starts. Use at the start of every editing job or stage (rough cut, graphics, B-roll, finishing, export, Premiere XML), and every time the user gives notes, corrections or feedback to act on, before touching anything.
---

# Edit plan

Its whole job: before any editing work, show the user what will happen, in what order, and
how long each step will take, so they know what to expect and can change the plan before
time is spent. This is a standing rule, not an option: no stage starts and no batch of notes
is acted on without a plan first.

## When

- The start of a new video or a new stage of one.
- Every time the user sends notes, corrections or a list of changes.
- When the plan changes mid-way (a render fails, a note turns out bigger than it looked):
  show the revised plan before carrying on.

A one-line answer or a question about the edit needs no plan.

## Video or Premiere XML?

At the start of a new video, work out which output the user wants:

- **A rendered video** (`rough-cut` and the later stages): they asked to edit, cut, rough-cut
  or make a short, and said nothing about Premiere.
- **A Premiere Pro XML** (`premiere-xml-cut`): they said Premiere, XML or timeline.
- **Both**: they asked for both.

If the request does not say, do not assume. Ask as the first line of the plan, "A finished
video, a Premiere XML, or both?", and wait for the answer before step 1. This is the one case
where the plan waits. Once a job's output is settled, later rounds of notes on that job need
not ask again.

## Measure before estimating

Estimates come from the actual inputs, never from a guess about them. First run:

- `ffprobe` on the footage: number of clips, total minutes, resolution, frame rate.
- How long the finished video is meant to be (from the style or the user).
- Which stages this job needs, from the request and the style.
- What already exists in the job folder (a saved transcript means no transcription step).
- The machine: `sysctl -n machdep.cpu.brand_string` (macOS) or `nproc` (Linux), and whether
  a hardware video encoder works here.

## Starting estimates

Rough times on a recent Apple Silicon Mac. Scale them by the measured inputs and replace
them with the times this machine actually takes (see "Learn from real times").

| Step                                         | Starting estimate                                      |
|----------------------------------------------|--------------------------------------------------------|
| First-ever setup of the transcription tool   | 10-20 min, once (3-5 GB download)                      |
| Transcription (WhisperX, CPU)                | 0.5-1.5 x the footage length                           |
| Reading the transcript, writing the cut sheet | 5-15 min per 10 min of footage                        |
| Rough-cut render, hardware encoder           | ~15 s per minute of output (1080p)                     |
| Rough-cut render, software encoder (4K)      | 1.5-2.5 min per minute of output                       |
| Graphics plan                                | 10-20 min                                              |
| Each graphic: build, render, check           | 5-15 min                                               |
| Composite graphics over the cut              | 1-3 min per minute of video                            |
| Generated B-roll clip                        | 3-10 min each                                          |
| Captions / music bed / sound effects         | 2-5 / 2-5 / 5-10 min                                   |
| One review pass (sub-agents, frame checks)   | 5-10 min                                               |
| Fix round after a review                     | 5-15 min per group of related notes, plus re-render    |
| Export and tidy                              | 1-3 min                                                |

Always add the review and at least one fix round to any step that renders.

## The plan the user sees

Short and plain. One line per step, in order:

```
Plan for <job> - <what this round does>

1. <step>  -  <what happens, in a few words>  -  ~<time>
2. ...

Total: about <time>. <What the user has to do, and when: e.g. "I'll need your answer on the
story after step 3 (about 25 min in)".>
Assumes: <the measured facts the estimates rest on: 42 min of 4K footage across 3 cameras, etc.>
```

- Give ranges when a step is uncertain ("10-20 min"), single numbers when it is not.
- Say which steps wait on the user, and roughly when they will be asked.
- For notes: one line per note (or per group of notes that touch the same thing), saying
  what will change and which part re-renders. Flag any note that conflicts with the style.
- Then start on step 1 (unless the output question above is still open). The user can stop
  or change the plan at any point.

## While working

- At the end of each step, one line: done, actual time vs estimate, what's next.
- If a step will overrun its estimate by more than about half, say so with the new estimate
  before carrying on, not after.

## Learn from real times

At the end of the job, compare actual times with the estimates. Where this machine is
consistently faster or slower (more than about half off, on two jobs or more), update the
"Starting estimates" table in this skill so the next plan is closer. Show the user the
change in one line.
