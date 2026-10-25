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
        * Played: a track whose pixels move most (a hand or a mallet on it), that a mallet box touches, or
          whose learned chakra the app hears now.
        * The percent on a mark is how steadily it is found (in 8 of the last 8 detections: 100 %), not
          OWL-ViT's score: that is no probability and stays near 0.1 to 0.3 even for a plain bowl.
        * Hear and see together: when the heard chakra changes to k (a new tone), the bowl track that
          moved most in the last ONSET_FRAMES frames gets a vote for k. After VOTES_NEEDED votes it is
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
LEAD = 0.8          # ... and only for the box that moves most, or nearly as much
EMA = 0.3           # how fast a box follows a new detection
CONFIRM = 2         # detections before a track is shown
SEEN_OF = 8         # the percent on a mark: found in how many of the last 8 detections
ONSET_FRAMES = 3    # how far back a moving bowl counts for a new tone
VOTES_NEEDED = 2
MAX_MARKS = 4
PLAYERS = {"Mallet"}
INSTRUMENTS = {"Singing bowl", "Gong", "Drum", "Tuning fork", "Chimes", "Rainstick"}


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
        self.box = [o + EMA * (n - o) for o, n in zip(self.box, box)]
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

    def need_detect(self, scene_change: float) -> bool:
        """Whether this frame needs the detector, from the whole picture's change since the last frame."""
        if scene_change > SCENE_CUT:
            # A person walking through or the camera moving: detect at once, but keep the bowls; where the
            # camera really moved they are not found again and age out after MISS_LIMIT detections.
            return True
        if not any(t.hits >= CONFIRM for t in self.tracks) or any(t.label in PLAYERS for t in self.tracks):
            return True
        return self.frame % REDETECT == 0

    def detections(self, found) -> None:
        """This frame's detections: [(label, x, y, w, h, score)], best first."""
        used = set()
        for label, *box, score in found:
            best, best_iou = None, IOU_MATCH
            for i, t in enumerate(self.tracks):
                if i in used or (label in PLAYERS) != (t.label in PLAYERS):
                    continue
                v = iou(box, t.box)
                if v >= best_iou:
                    best, best_iou = i, v
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

    def step(self, motions, heard: int):
        """After detections() (or without, on a skipped frame): the motion inside each track's box, in
        self.tracks' order, and the heard chakra (-1 none). Returns the marks
        [(label, x, y, w, h, score, played)]."""
        self.frame += 1
        for t in self.tracks:
            t.missed += 1  # frames since it was last found; update() sets it back to 0
        for t, m in zip(self.tracks, motions):
            t.motion = t.motion[1:] + [m]
        if heard != self.heard and heard >= 0:
            self.vote(heard)
        self.heard = heard
        shown = [t for t in self.tracks if t.hits >= CONFIRM]
        players = [t for t in shown if t.label in PLAYERS]
        marks = []
        # Moving means clearly the most: a hand passing over the row stirs every box a little.
        top = max((t.motion[-1] for t in shown if t.label not in PLAYERS), default=0.0)
        for t in shown:
            played = 0
            if t.label not in PLAYERS:
                moving = t.motion[-1] > MOTION and t.motion[-1] >= LEAD * top
                touched = any(iou(t.box, p.box) > 0.0 for p in players)
                sounding = t.chakra >= 0 and t.chakra == heard
                played = 1 if moving or touched or sounding else 0
            label = f"Bowl {NOTES[t.chakra]}" if t.label == "Singing bowl" and t.chakra >= 0 else t.label
            marks.append(((label, *[round(v, 3) for v in t.box], round(t.steady, 2), played), t.score))
        marks.sort(key=lambda m: (-m[0][6], -m[0][5], -m[1]))
        return [m[0] for m in marks[:MAX_MARKS]]

    def vote(self, k: int) -> None:
        bowls = [t for t in self.tracks if t.hits >= CONFIRM and t.label in INSTRUMENTS]
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
    print("self-test ok")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--self-test", action="store_true")
    if ap.parse_args().self_test:
        self_test()
