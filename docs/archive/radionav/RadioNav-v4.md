# RadioNav: Communication-Constrained Navigation via Future Wireless Signal Prediction

## Project Plan v4 (Frozen Scope)

## 1. Core Idea

Existing visual navigation policies optimize reaching goals, avoiding
collisions, and minimizing path length, but usually ignore future
wireless connectivity.

We propose a communication-constrained navigation framework that
predicts future wireless signal quality along candidate trajectories and
enables navigation policies to avoid connectivity failures.

Core idea:

Future Wireless Prediction -\> Communication-Aware Trajectory Selection

------------------------------------------------------------------------

## 2. Scope Boundary

### We Do

-   Use X-NavDP as the navigation backbone.
-   Add wireless communication dynamics into the navigation environment.
-   Predict future wireless quality along candidate trajectories.
-   Select trajectories considering navigation and communication
    jointly.

### We Do NOT Do (First Version)

-   ObjectNav.
-   VLM/LLM reasoning.
-   Frontier exploration.
-   AP localization.
-   End-to-end RL training.

First version:

Frozen X-NavDP + Future Wireless Signal Prediction + Communication-Aware
Trajectory Selection.

------------------------------------------------------------------------

## 3. System Overview

RGB-D + PointGoal

↓

X-NavDP

↓

Candidate trajectories

↓

Navigation Critic + Future Signal Predictor

↓

Communication-aware trajectory score

↓

Execute trajectory

------------------------------------------------------------------------

## 4. Communication Environment

Extend indoor navigation scenes with:

-   indoor scene;
-   robot;
-   goal;
-   wireless AP.

Each episode contains:

-   scene;
-   AP placement;
-   start;
-   goal.

The environment provides:

RSSI = f(x,y)

Robot receives RSSI according to its position.

------------------------------------------------------------------------

## 5. Future Wireless Signal Predictor

Input:

-   historical RSSI observations;
-   robot motion history;
-   candidate trajectory;
-   local geometry;
-   AP information.

Output:

-   future RSSI sequence;
-   outage probability;
-   uncertainty.

------------------------------------------------------------------------

## 6. Communication-Aware Trajectory Selection

Original X-NavDP:

J = Q_nav

Our method:

J = Q_nav - lambda \* C_comm

where C_comm is predicted communication risk.

------------------------------------------------------------------------

## 7. Training Strategy

Phase 0: Reproduce X-NavDP.

Phase 1: Build communication benchmark with AP and RSSI maps.

Phase 2: Train future signal predictor using:

Input: - past RSSI history; - motion history; - trajectory; -
geometry; - AP information.

Output: - future RSSI; - outage prediction.

------------------------------------------------------------------------

## 8. Evaluation

Main comparison:

  Method           Description
  ---------------- ------------------------------------------
  X-NavDP          Original navigation policy
  X-NavDP + Ours   Communication-aware trajectory selection

Metrics:

Navigation: - Success Rate - SPL

Communication: - Outage Ratio - Longest Outage - Minimum RSSI

Main metric:

Communication-Constrained Success Rate:

Goal reached AND connectivity maintained.

------------------------------------------------------------------------

## 9. Final Contribution

1.  A communication-constrained navigation environment with wireless
    connectivity dynamics.

2.  A future trajectory-conditioned wireless signal predictor.

3.  A communication-aware trajectory selection method improving
    navigation reliability without modifying the navigation backbone.

Final:

X-NavDP + Future Wireless Signal Prediction + Communication-Aware
Trajectory Selection
