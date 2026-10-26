#!/usr/bin/env python3
"""Keeps the instruments the detector found, frame to frame, and learns which bowl sounds which note.

What: detect_owl.py hands each frame's detections, the motion inside every box and the chakra the app
      heard (the simulator's "heard" line) to a Tracker, which returns the marks to draw:
        * Bowls stay. A detection that overlaps a known track by IOU_MATCH or more updates it (box and
          score smoothed by EMA); a track missed by a detection stays for MISS_LIMIT detections, since
          bowls are rarely moved. Its label is the one it was detected as most often, so a bowl that is
          once taken for a gong stays a singing bowl.
        * Detection is not needed every frame: need_detect() says when (every REDETECT frames, at once
          when no track is confirmed, when the whole picture changes (a person passing, the camera moved:
          the bowls stay, and age out only after MISS_LIMIT frames unfound), and
          every frame while a mallet is in view, because a mallet moves).
        * Helpers: a hand or a mallet plays the bowl it covers most; a "bowl" found on a foot or a head
          is dropped; helpers are never drawn. Two tracks on one bowl are merged.
        * Played: a track whose pixels move most (a hand or a mallet on it), that a hand or mallet covers, or
          whose learned chakra the app hears now.
        * The percent on a mark is how steadily it is found (in 8 of the last 8 detections: 100 %), not
          OWL-ViT's score: that is no probability and stays near 0.1 to 0.3 even for a plain bowl.
        * A chakra set in a row (7 bowls): from 3 or more strikes with the mallet seen, it learns which end
          of the row is C and names all 7 at once ("Bowl C" .. "Bowl B"); single strikes are often one
          bowl off, the direction is not. The mallet head is found by its colour (detect_owl).
        * Hear and see together: when the heard chakra changes to k (a new tone), the bowl a hand or
          mallet covered in the last ONSET_FRAMES frames gets a vote for k (the one covered last if
          several), failing that the bowl that moved most. After VOTES_NEEDED votes it is
          that chakra's bowl, labelled with its note ("Bowl C"), and marked played whenever k sounds,
          even with the hand out of the picture.
      Notes: the Indian seven-chakra system, as in chakra_detect.c: C Root, D Sacral, E Solar plexus,
      F Heart, G Throat, A Third eye, B Crown (the Nepalese system is not used).
Why:  owner 25.10.2026: "Singing bowls, wenn erkannt, bleiben ja Singing bowls ... muss ja nicht jedes
      Frame komplett neu bewerten" and "beim Anschlagen ist der Schlägel und Detection immer hilfreich,
      kann man das alles mit reingeben".
Pitfalls:
  * The app draws at most 4 marks: played ones first, then the best scores.
  * A vote needs exactly one clearly moving bowl; with two hands on two bowls nobody gets it.
  * Pure Python, no numpy: detect_owl measures the motion, this only decides.
Usage:  bowl_tracker.py --self-test
"""
import argparse

NOTES = ["C", "D", "E", "F", "G", "A", "B"]  # chakra 0..6, Root to Crown
IOU_MATCH = 0.3
MISS_LIMIT = 40     # frames (20 s at 2 fps) a bowl may go unfound before it is dropped: bowls rarely move,
                    # and a person bending over the row hides them all for seconds (25.10.2026 video)
REDETECT = 4        # frames between detections while the scene is still
SCENE_CUT = 25.0    # mean change of the whole picture (0..255) that means the camera moved
MOTION = 14.0       # mean change inside a box that counts as moving
LEAD = 0.8
SPIKE, SPIKE_MIN = 2.5, 5.0  # ... or 2.5 times the box's usual motion and over 5: a stick struck gently
QUIET_EMA = 0.1              # (a YouTube tune-up, 26.10.2026: strikes moved a big bowl's box by 4 to 8)          # ... and only for the box that moves most, or nearly as much
EMA = 0.3           # how fast a box follows a new detection
EMA_MOVED = 0.8     # ... and when it moved (a bowl lifted into the hands, 26.10.2026)
FOLLOW = 0.8        # a detection this close (times the box's size) to a track of its label is that track moved
CONFIRM = 2         # detections before a track is shown
SEEN_OF = 8         # the percent on a mark: found in how many of the last 8 detections
ONSET_FRAMES = 3    # how far back a moving bowl counts for a new tone
VOTES_NEEDED = 2
ROW_GAP = 2.5       # a bowl this many median gaps beyond the row's end is not part of the set
ROW_CORR = 0.8      # how clearly the notes must rise (or fall) along the row before all bowls are named
MAX_MARKS = 7       # the owner plays 7 chakra bowls; the app draws CHAKRA_BOXES of them
SHOW_STEADY = 0.25  # a track found in fewer than a quarter of the last detections is no longer drawn
PLAYERS = {"Mallet", "Hand"}  # these play an instrument they are on; tracked only where last seen
BLOCKERS = {"Foot", "Leg", "Head"}  # a "bowl" found on one of these is that, not a bowl (a foot was, 25.10.2026)
HIDDEN = {"Hand"} | BLOCKERS  # helpers, never drawn
PLAYER_MOVE = 5.0   # a hand or mallet box must change this much (0..255) to count as playing
TOUCH = 0.15        # a player covering this share of a bowl touches it (the bowl it covers most)
DUPLICATE = 0.75    # two tracks of one label whose overlap covers this share of the smaller are one
INSTRUMENTS = {"Singing bowl", "Gong", "Drum", "Tuning fork", "Chimes", "Rainstick"}


def inter(a, b) -> float:
    w = max(0.0, min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0]))
    h = max(0.0, min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1]))
    return w * h


def iou(a, b) -> float:
    ax2, ay2, bx2, by2 = a[0] + a[2], a[1] + a[3], b[0] + b[2], b[1] + b[3]
    w, h = max(0.0, min(ax2, bx2) - max(a[0], b[0])), max(0.0, min(ay2, by2) - max(a[1], b[1]))
    inter = w * h
    return inter / (a[2] * a[3] + b[2] * b[3] - inter + 1e-9)


class Track:
    def __init__(self, label: str, box, score: float):
        self.labels = {label: 1}
        self.box, self.score = list(box), score
        self.hits, self.missed = 1, 0
        self.found = [1]  # the last SEEN_OF detections: 1 found, 0 missed
        self.motion = [0.0] * ONSET_FRAMES
        self.touch = [0] * ONSET_FRAMES
        self.quiet = None  # the box's usual motion (EMA), so a short spike shows a gentle strike  # 1 where a hand or mallet covered it, the last ONSET_FRAMES frames
        self.votes = [0] * len(NOTES)

    @property
    def label(self) -> str:
        return max(self.labels, key=self.labels.get)

    @property
    def chakra(self) -> int:
        best = max(range(len(NOTES)), key=lambda k: self.votes[k])
        return best if self.votes[best] >= VOTES_NEEDED else -1

    def update(self, label: str, box, score: float) -> None:
        self.labels[label] = self.labels.get(label, 0) + 1
        k = EMA if iou(box, self.box) >= 0.5 else EMA_MOVED  # lifted or moved: follow quickly
        self.box = [o + k * (n - o) for o, n in zip(self.box, box)]
        self.score += EMA * (score - self.score)
        self.hits, self.missed = self.hits + 1, 0
        self.found = (self.found + [1])[-SEEN_OF:]

    @property
    def steady(self) -> float:
        """The share of the last SEEN_OF detections that found it: the mark's percent."""
        return sum(self.found) / max(4, len(self.found))  # a new one climbs to 100 % in 4 detections


class Tracker:
    def __init__(self):
        self.tracks: list[Track] = []
        self.frame = 0
        self.heard = -1
        self.mallet = None   # (x, y) of the mallet's head this frame, from its colour (detect_owl)
        self.trail = []      # the bowl the mallet head was on, the last ONSET_FRAMES frames (track ids)
        self.pairs = []      # (chakra heard, rank of the bowl along the row) for each new tone with a mallet
        self.direction = 0   # +1: the row's first bowl is C, -1: it is B; 0 not learned yet

    def row(self) -> list:
        """The bowls standing on one straight line (the set), in order from the nearest (lowest in the
        picture). Spare bowls beside it are left out: of every line through two bowl centres, the one
        that passes closest to the most centres wins (within half a bowl's width)."""
        bowls = [t for t in self.tracks if t.label == "Singing bowl" and t.hits >= CONFIRM]
        if len(bowls) < 3:
            return []
        c = [(t.box[0] + t.box[2] / 2, t.box[1] + t.box[3] / 2) for t in bowls]
        best = []
        for i in range(len(bowls)):
            for j in range(i + 1, len(bowls)):
                dx, dy = c[j][0] - c[i][0], c[j][1] - c[i][1]
                n = (dx * dx + dy * dy) ** 0.5
                if n < 1e-6:
                    continue
                on = [k for k in range(len(bowls))
                      if abs((c[k][0] - c[i][0]) * dy - (c[k][1] - c[i][1]) * dx) / n < 0.5 * bowls[k].box[2]]
                if len(on) > len(best):
                    best, axis = on, (dx / n, dy / n)
        if len(best) < 3:
            return []
        ux, uy = axis if axis[1] < 0 else (-axis[0], -axis[1])  # pointing up the picture
        row = sorted((bowls[k] for k in best),
                     key=lambda t: (t.box[0] + t.box[2] / 2) * ux + (t.box[1] + t.box[3] / 2) * uy)
        # A set stands close together: something further along the same line (a bowl on a shelf in
        # the back, 25.10.2026) is cut off where the gap is far wider than the row's own gaps.
        pos = [(t.box[0] + t.box[2] / 2) * ux + (t.box[1] + t.box[3] / 2) * uy for t in row]
        gaps = [b - a for a, b in zip(pos, pos[1:])]
        if len(gaps) >= 3:
            mid = sorted(gaps)[len(gaps) // 2]
            while len(row) > 3 and gaps and gaps[-1] > ROW_GAP * mid:
                row, gaps = row[:-1], gaps[:-1]
            while len(row) > 3 and gaps and gaps[0] > ROW_GAP * mid:
                row, gaps = row[1:], gaps[1:]
        return row

    def mallet_bowl(self):
        """The bowl the mallet head is on: of the boxes holding it, the one whose far rim (top edge) is nearest."""
        if not self.mallet:
            return None
        x, y = self.mallet
        inside = [t for t in self.tracks if t.label == "Singing bowl" and t.hits >= CONFIRM and
                  t.box[0] - 0.03 <= x <= t.box[0] + t.box[2] + 0.03 and t.box[1] - 0.05 <= y <= t.box[1] + t.box[3]]
        return min(inside, key=lambda t: abs(t.box[1] - y)) if inside else None

    def need_detect(self, scene_change: float) -> bool:
        """Whether this frame needs the detector, from the whole picture's change since the last frame."""
        if scene_change > SCENE_CUT:
            # A person walking through or the camera moving: detect at once, but keep the bowls; where the
            # camera really moved they are not found again and age out after MISS_LIMIT detections.
            return True
        if not any(t.hits >= CONFIRM for t in self.tracks) or any(t.label in PLAYERS for t in self.tracks):
            return True
        if any(t.motion[-1] > MOTION for t in self.tracks) or self.mallet:
            return True  # something is being moved or played: look every frame, a lifted bowl must follow
        return self.frame % REDETECT == 0

    def detections(self, found) -> None:
        """This frame's detections: [(label, x, y, w, h, score)], best first."""
        blockers = [f[1:5] for f in found if f[0] in BLOCKERS]
        found = [f for f in found if f[0] not in BLOCKERS and
                 not (f[0] not in PLAYERS and any(inter(f[1:5], b) > 0.5 * f[3] * f[4] for b in blockers))]
        used = set()
        for label, *box, score in found:
            best, best_iou = None, IOU_MATCH
            for i, t in enumerate(self.tracks):
                if i in used or (label in PLAYERS) != (t.label in PLAYERS):
                    continue
                v = iou(box, t.box)
                if v >= best_iou:
                    best, best_iou = i, v
            if best is None and label not in PLAYERS:
                # Moved rather than new: the nearest track of its kind whose size fits, within FOLLOW sizes.
                cx, cy = box[0] + box[2] / 2, box[1] + box[3] / 2
                near = []
                for i, t in enumerate(self.tracks):
                    if i in used or t.label in PLAYERS or t.label != label:
                        continue
                    size = max(t.box[2], t.box[3])
                    ratio = (box[2] * box[3]) / (t.box[2] * t.box[3] + 1e-9)
                    d = ((t.box[0] + t.box[2] / 2 - cx) ** 2 + (t.box[1] + t.box[3] / 2 - cy) ** 2) ** 0.5
                    if d < FOLLOW * size and 0.4 < ratio < 2.5:
                        near.append((d, i))
                if near:
                    best = min(near)[1]
            if best is None:
                self.tracks.append(Track(label, box, score))
                used.add(len(self.tracks) - 1)
            else:
                self.tracks[best].update(label, box, score)
                used.add(best)
        for i, t in enumerate(self.tracks):
            if i not in used:
                t.found = (t.found + [0])[-SEEN_OF:]
                if t.label in PLAYERS:
                    t.missed = MISS_LIMIT + 1  # a mallet is only where it was last seen
        self.tracks = [t for t in self.tracks if t.missed <= MISS_LIMIT]
        self.merge()

    def merge(self) -> None:
        """One bowl, one track: OWL often finds a bowl twice (the bowl, and the bowl with its shadow)."""
        keep = []
        for t in sorted(self.tracks, key=lambda t: -t.hits):
            twin = next((k for k in keep if k.label == t.label and t.label not in PLAYERS and
                         inter(t.box, k.box) > DUPLICATE * min(t.box[2] * t.box[3], k.box[2] * k.box[3])), None)
            if twin is None:
                keep.append(t)
            else:
                twin.votes = [a + b for a, b in zip(twin.votes, t.votes)]
        self.tracks = keep

    def step(self, motions, heard: int):
        """After detections() (or without, on a skipped frame): the motion inside each track's box, in
        self.tracks' order, and the heard chakra (-1 none). Returns the marks
        [(label, x, y, w, h, score, played)]."""
        self.frame += 1
        for t in self.tracks:
            t.missed += 1  # frames since it was last found; update() sets it back to 0
        for t, m in zip(self.tracks, motions):
            t.motion = t.motion[1:] + [m]
            t.spike = t.quiet is not None and m > SPIKE_MIN and m > SPIKE * t.quiet
            t.quiet = m if t.quiet is None else t.quiet + QUIET_EMA * (min(m, 2 * t.quiet + 1) - t.quiet)
        shown = [t for t in self.tracks if t.hits >= CONFIRM]
        players = [t for t in shown if t.label in PLAYERS]
        marks = []
        # Moving means clearly the most: a hand passing over the row stirs every box a little.
        top = max((t.motion[-1] for t in shown if t.label not in PLAYERS), default=0.0)
        # A hand or a mallet touches the one bowl it covers most, not every box it grazes.
        touched_ids = set()
        for p in players:
            # A mallet lying on a bowl plays nothing: only a moving hand or mallet counts (a tune-up video
            # had its mallet resting on a bowl, and that bowl was "played" in 86 % of frames, 26.10.2026).
            if p.motion[-1] <= PLAYER_MOVE:
                continue
            cover = [(inter(p.box, t.box) / (t.box[2] * t.box[3] + 1e-9), id(t)) for t in shown if t.label not in PLAYERS]
            if cover and max(cover)[0] > TOUCH:
                touched_ids.add(max(cover)[1])
        for t in self.tracks:
            t.touch = t.touch[1:] + [1 if id(t) in touched_ids else 0]
        on = self.mallet_bowl()
        self.trail = (self.trail + [id(on) if on else None])[-ONSET_FRAMES:]
        if heard != self.heard and heard >= 0:
            self.vote(heard)  # after this frame's touches: the hand on the bowl as the tone starts
            self.learn_row(heard)
        self.heard = heard
        # One bowl per note: the track with the most votes for it keeps the name (two were "Bowl G", 26.10.2026).
        owner = {}
        for t in shown:
            k = t.chakra
            if k >= 0 and (k not in owner or t.votes[k] > owner[k].votes[k]):
                owner[k] = t
        for t in shown:
            if t.label in HIDDEN or (t.steady < SHOW_STEADY and t.chakra < 0):  # a named set's bowl stays put
                continue
            played = 0
            if t.label not in PLAYERS:
                moving = (t.motion[-1] > MOTION and t.motion[-1] >= LEAD * top) or getattr(t, "spike", False)
                touched = id(t) in touched_ids
                sounding = t.chakra >= 0 and t.chakra == heard
                played = 1 if moving or touched or sounding else 0
            named = t.label == "Singing bowl" and t.chakra >= 0 and owner.get(t.chakra) is t
            label = f"Bowl {NOTES[t.chakra]}" if named else t.label
            marks.append(((label, *[round(v, 3) for v in t.box], round(t.steady, 2), played), t.score))
        # The bowls of a named set first (played ones first among them), then the rest: a stray moving
        # "tuning fork" at the player's feet must not push a set's bowl out of the app's 7 (25.10.2026).
        if self.mallet and not players:
            # The mallet's head by its colour (detect_owl): drawn where the model did not find a mallet box.
            x, y = self.mallet
            marks.append((("Mallet", round(max(0.0, x - 0.04), 3), round(max(0.0, y - 0.04), 3), 0.08, 0.08, 1.0, 0), 0.0))
        marks.sort(key=lambda m: (not m[0][0].startswith("Bowl "), -m[0][6], -m[0][5], -m[1]))
        return [m[0] for m in marks[:MAX_MARKS]]

    def learn_row(self, k: int) -> None:
        """A chakra set in a row: learn from a few strikes which end is C, then name all bowls at once.
        Single strikes are often one bowl off (a strike on a far rim lands in the next bowl's box), the
        direction is not (25.10.2026, the owner's 7 bowls, 5 of 7 strikes in the right box)."""
        row = self.row()
        ids = [i for i in self.trail if i is not None]
        if len(row) != len(NOTES) or not ids:
            return
        rank = next((r for r, t in enumerate(row) if id(t) == ids[-1]), None)
        if rank is None:
            return
        self.pairs = (self.pairs + [(k, rank)])[-12:]
        if len(self.pairs) < 3:
            return
        n = len(self.pairs)
        mk, mr = sum(p[0] for p in self.pairs) / n, sum(p[1] for p in self.pairs) / n
        cov = sum((p[0] - mk) * (p[1] - mr) for p in self.pairs)
        vk = sum((p[0] - mk) ** 2 for p in self.pairs) ** 0.5
        vr = sum((p[1] - mr) ** 2 for p in self.pairs) ** 0.5
        corr = cov / (vk * vr + 1e-9)
        if abs(corr) >= ROW_CORR:
            self.direction = 1 if corr > 0 else -1
            for r, t in enumerate(row):
                t.votes = [0] * len(NOTES)
                t.votes[r if self.direction > 0 else len(NOTES) - 1 - r] = VOTES_NEEDED

    def vote(self, k: int) -> None:
        """A new tone k: the bowl a hand or mallet was on gets the vote; failing that, the one that moved most.
        A person leaning over the row stirs several boxes, so the touch is the better witness (25.10.2026)."""
        bowls = [t for t in self.tracks if t.hits >= CONFIRM and t.label in INSTRUMENTS]
        if self.direction:
            return  # the row is learned; single votes would only add noise
        on = [i for i in self.trail if i is not None]
        if on:
            hit = next((t for t in bowls if id(t) == on[-1]), None)
            if hit:
                hit.votes[k] += 1
                return
        touched = [t for t in bowls if any(t.touch)]
        if len(touched) == 1:
            touched[0].votes[k] += 1
            return
        if touched:
            # Several touched in the window (the hand moves on): the one touched last before the tone.
            last = max(touched, key=lambda t: max(i for i, v in enumerate(t.touch) if v))
            if sum(1 for t in touched if t.touch[-1] == last.touch[-1] and
                   max(i for i, v in enumerate(t.touch) if v) == max(i for i, v in enumerate(last.touch) if v)) == 1:
                last.votes[k] += 1
            return
        moving = sorted(bowls, key=lambda t: -max(t.motion))
        if not moving or max(moving[0].motion) <= MOTION:
            return
        if len(moving) > 1 and max(moving[1].motion) > 0.7 * max(moving[0].motion):
            return  # two bowls move alike: no telling which one sounded
        moving[0].votes[k] += 1


def self_test() -> None:
    tr = Tracker()
    bowl_a, bowl_b = (0.1, 0.1, 0.2, 0.2), (0.6, 0.6, 0.2, 0.2)
    for f in range(12):
        found = [("Singing bowl", *bowl_a, 0.3), ("Gong" if f == 5 else "Singing bowl", *bowl_b, 0.25)]
        if tr.need_detect(1.0):
            tr.detections(found if f != 7 else [found[0]])  # frame 7: bowl b is missed once
        m = tr.step([0.0, 0.0], -1)
    assert len(m) == 2 and all(x[0] == "Singing bowl" for x in m), m  # b stayed, and stayed a bowl
    for k in range(2):  # bowl a is struck while C sounds, twice
        tr.step([30.0, 0.0], -1)
        m = tr.step([30.0, 0.0], 0)
        tr.step([0.0, 0.0], -1)
    m = tr.step([0.0, 0.0], 0)  # C sounds again, the hand is gone
    assert m[0][0] == "Bowl C" and m[0][6] == 1, m
    assert tr.need_detect(40.0) and len(tr.tracks) == 2  # a person walks through: detect, keep the bowls
    for _ in range(MISS_LIMIT + 2):
        tr.detections([("Singing bowl", 0.4, 0.4, 0.2, 0.2, 0.3)])  # the camera moved: new place
        tr.step([0.0] * len(tr.tracks), -1)
    assert [t.box[:2] for t in tr.tracks] == [[0.4, 0.4]], [t.box for t in tr.tracks]  # the old ones aged out
    tr = Tracker()
    for _ in range(3):  # a foot found as a bowl, and found as a foot: no bowl
        tr.detections([("Singing bowl", 0.0, 0.5, 0.2, 0.2, 0.2), ("Foot", 0.0, 0.48, 0.25, 0.25, 0.3)])
        m = tr.step([0.0] * len(tr.tracks), -1)
    assert m == [], m
    tr = Tracker()
    for _ in range(3):  # one bowl found twice, and a hand on it
        tr.detections([("Singing bowl", 0.3, 0.3, 0.2, 0.2, 0.4), ("Singing bowl", 0.31, 0.3, 0.2, 0.24, 0.3),
                       ("Singing bowl", 0.7, 0.3, 0.2, 0.2, 0.3), ("Hand", 0.35, 0.35, 0.1, 0.1, 0.3)])
        m = tr.step([10.0 if t.label == "Hand" else 0.0 for t in tr.tracks], -1)  # the hand moves
    assert len(m) == 2 and [x[6] for x in m] == [1, 0] and m[0][1] < 0.5, m  # merged, the hand's bowl played
    for _ in range(3):  # the same hand lying still plays nothing
        tr.detections([("Singing bowl", 0.3, 0.3, 0.2, 0.2, 0.4), ("Singing bowl", 0.7, 0.3, 0.2, 0.2, 0.3),
                       ("Hand", 0.35, 0.35, 0.1, 0.1, 0.3)])
        m = tr.step([0.0] * len(tr.tracks), -1)
    assert [x[6] for x in m] == [0, 0], m
    tr = Tracker()  # a row of 7, the nearest (lowest) is C; the mallet strikes C, E, G, B
    row7 = [(0.4, 0.80 - 0.1 * r, 0.1, 0.08) for r in range(7)]
    for _ in range(3):
        tr.detections([("Singing bowl", *b, 0.3) for b in row7])
        tr.step([0.0] * len(tr.tracks), -1)
    for k in (0, 2, 4, 6):
        b = row7[k]
        tr.mallet = (b[0] + 0.05, b[1] + 0.01)
        tr.step([0.0] * len(tr.tracks), -1)
        m = tr.step([0.0] * len(tr.tracks), k)
    tr.mallet = None
    m = tr.step([0.0] * len(tr.tracks), -1)
    names = {round(x[2], 2): x[0] for x in m}
    assert tr.direction == 1 and names[0.8] == "Bowl C" and names[0.2] == "Bowl B", (tr.direction, names)
    tr = Tracker()  # a bowl lifted: found 0.12 up and to the side, it must follow, not stay and double
    for _ in range(3):
        tr.detections([("Singing bowl", 0.40, 0.50, 0.16, 0.12, 0.3)])
        tr.step([0.0], -1)
    for _ in range(2):
        tr.detections([("Singing bowl", 0.46, 0.40, 0.16, 0.12, 0.3)])
        m = tr.step([20.0] * len(tr.tracks), -1)
    assert len(tr.tracks) == 1 and abs(tr.tracks[0].box[1] - 0.40) < 0.02, [t.box for t in tr.tracks]
    print("self-test ok")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--self-test", action="store_true")
    if ap.parse_args().self_test:
        self_test()
