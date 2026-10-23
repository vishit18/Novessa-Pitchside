# Glossary

What the numbers on screen mean. Each `##` section becomes one search document
(`scripts/index_knowledge.py`). Keep entries short, plain and true to how the state engine
computes them (docs/03, section 6). No match results here: this is background, never a spoiler.

## Possession
The share of the ball each side has had. We show it two ways: over the whole match, and over
the last five minutes. The five-minute number moves fast and tells you who has the ball now;
the whole-match number tells you the shape of the game so far.

## Momentum
A single bar from -100 to 100 that leans towards whichever side is on top right now. It weighs
recent territory, shots, expected goals and entries into the final third, and older actions
fade away, so a spell of pressure shows up within a minute and drains away when it stops.
Momentum is not a prediction. A side can lead on momentum and still concede.

## Pressure index
How hard a team is pressing, from 0 to 100. It counts pressing actions for every pass the
opponent makes in their own half, over a rolling window, a bit like PPDA turned the right way
up: higher means more pressing. A jump in the pressure index usually means a side has pushed
its line up and is trying to win the ball back early.

## Control and chaos
The control-chaos index runs from calm to chaotic. Long possessions, few turnovers and a
compact shape read as control. Quick turnovers, transitions, a stretched shape and fouls read
as chaos. Matches swing between the two; the flip from control to chaos is often when goals
come.

## Rhythm and tempo
Tempo is events per minute: passes, carries, duels, shots. Rhythm adds the average length of a
possession and flags when the pattern breaks, for example after an injury stoppage or a
substitution, when a tidy passing game turns into long balls.

## Pass difficulty
Every pass gets a difficulty score from 0 to 100, with the reasons that made it hard: distance,
defenders near the passing lane, pressure on the passer, how tightly the receiver is marked,
the angle (forward passes and switches are harder than going backwards), lofted balls, the
weak foot, and first-time passes. A typical pass scores in the twenties. Above 70 is rare and
above 80 is one we flag on screen.

## Expected goals (xG)
The chance a shot becomes a goal, from 0 to 1, based on distance, angle, pressure on the
shooter and the body part used. A penalty is worth 0.76. A player's xG is the total from all
of their shots so far, not the value of one shot. Scoring more than your xG means finishing
well, or luck; scoring less means good goalkeeping, poor finishing, or luck.

## Big chance
A shot with a high xG: a clear look at goal that a striker would expect to score more often
than not. Missed big chances are where matches turn.

## Sprints and top speed
A sprint is a burst above 30 km/h. Top speed is the fastest a player has run so far in the
match. Distance covered is everything they have run, in kilometres; a full-back or a box to
box midfielder usually covers the most.

## Ball speed and shot speed
How fast the ball travels, in km/h, worked out from the tracking data over the flight of the
pass or shot. A shot over 100 km/h is one we flag.

## Duels
A one against one contest for the ball: a tackle, a fifty-fifty or an aerial challenge. Duels
won counts the ones a player came out of with the ball, or with the ball safe for their side.

## Ball wins
The times a team took the ball off the opponent, through a tackle, an interception or a loose
ball recovered. A pressing side racks up ball wins high up the pitch.

## Penalties
A foul by a defender inside their own box gives a penalty. The shot from the spot is worth 0.76
xG. Penalties taken and penalties scored are counted per player.

## Cards
A yellow card is a caution. A second yellow, or a straight red, sends the player off and the
side plays on with ten. We count yellows and reds per player.

## Significance
How much a moment matters, from 0 to 100, scored by code before any agent sees it. Goals, big
chances, momentum swings, red cards and sudden changes in pressure score highest. The producer
uses it to choose what goes on air.

## Verified
Every number in an answer or a graphic is checked against the computed match data before it
airs. If a number cannot be found, the text is sent back once, and if it still does not check
out the viewer gets the numbers on their own instead.
