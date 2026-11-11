# The opening-scene prompt

One prompt per keyword. One shot. The scene has two jobs: show what the keyword names in
the first second, and look like it was filmed on the same day as the rest of the video.

## Before writing

From `look-sheet.jpg`, write down four things about the seller's video and reuse them in
every prompt word for word:

- **Place and time:** "a stone fire pit in a field at dusk"
- **Light:** "the campfire is the only light, warm amber on faces, dark beyond it with detail still visible"
- **People:** "a father in his thirties and a boy of about seven" (or "no people, hands only")
- **Camera feel:** "handheld weight, shallow depth of field, 35mm"

From the product images, write the **product identity** sentence: what it is, its exact
shape, colours, materials and how many pieces are in frame. Counts matter: say "one stick
in each hand", never "sticks".

## What the keyword changes

Only the thing the keyword names. Ask which kind it is:

| The keyword names | The scene changes |
|---|---|
| a food or material ("hot dog", "vegetable") | what is on, in or under the product |
| a person ("for kids", "for seniors") | who is using it |
| a place or occasion ("camping", "backyard bbq") | where it is used |
| a feature ("extendable", "foldable") | the feature happening on camera |

Everything else stays the video's own world.

## The prompt

The CAMERA block comes first, on its own. A camera move written inside the action
sentence gets ignored; a camera block at the top gets followed.

```
CAMERA: One continuous shot, it does not cut. [Height and lens feel from the video.] [One
simple move: a slow push in / a slow lateral drift / locked off.]

SUBJECT: [who and where, from the video's own world]. [The keyword's thing, visible and
unmistakable within the first second, with the product in use.] [One small human moment:
a look, a laugh, a reaction.]

COMPOSITION: The subject sits in [the upper / the lower] two thirds of the frame. The
[bottom / top] third of the frame stays darker and uncluttered: no face, no hand and
none of [the keyword's thing] in it.

LIGHT: [The video's light, word for word.]

SOUND: [Only sounds that belong to the scene.] No music, no speech.

PRODUCT IDENTITY: [The identity sentence.] The product matches the reference images
exactly. The reference images show the product only; do not copy their backgrounds,
props, text or layout.

NEVER: no text, no captions, no logos, no watermarks, no split screen, no extra products,
[anything from the references that must not leak in], [the obvious wrong version of this
keyword].
```

The COMPOSITION line is there for the title, which is large. It needs one calm band, the
bottom third or the top third. Pick the one the scene can spare, say so, and write the
same band into that variant's `"place"` in plan.json (`"top"` or `"bottom"`). Left on
`auto` the build only guesses, and by firelight it guesses the band with the faces.

Keep the scene about as bright as the video's own first shot. The ad plays small; an
opening that is mostly black disappears next to the results around it.

## Worked example

Video: a family roasting marshmallows at a campfire at dusk. Product: telescoping roasting
sticks. Keyword: **hot dog roasting sticks**.

```
CAMERA: One continuous shot, it does not cut. Chest height, 35mm feel, shallow depth of
field. A slow push in from a medium two-shot toward the hot dogs over the fire. Handheld
weight, no shake.

SUBJECT: A father in his thirties and a boy of about seven sit close together at a stone
fire pit in a field at dusk. Each holds one roasting stick over the flames with one hot
dog on its two-prong fork, the skins just starting to blister. The boy looks up at his
father and grins.

COMPOSITION: The two of them, the hot dogs and the fire sit in the lower two thirds of
the frame. The top third of the frame is dusk sky and treeline, uncluttered: no face, no
hand and no hot dog in it.

LIGHT: The campfire is the only light: warm amber on faces and steel, the field beyond
the fire ring dark but still readable, a last cool blue of dusk above the treeline.

SOUND: Fire crackle, a faint sizzle, quiet evening insects. No music, no speech.

PRODUCT IDENTITY: A telescoping stainless steel roasting stick with a U-shaped two-prong
fork at the tip and a coloured wooden handle. One stick in each person's hand, two sticks
in total. The product matches the reference images exactly. The reference images show the
product only; do not copy their backgrounds, props, text or layout.

NEVER: no text, no captions, no logos, no watermarks, no split screen, no bundle of spare
sticks, no kitchen table, no marshmallows, no buns, no plates, no grill grate.
```

## When a scene comes back wrong

Fix the sentence that caused it, not the whole prompt:

- Wrong product shape or count: tighten PRODUCT IDENTITY, add the wrong version to NEVER.
- Something from a listing photo leaked in (a white table, an infographic layout): name it
  in NEVER.
- A feature that seems to work by magic (a stick that grows with no hand pulling it): add
  a reference video of the real motion and a REFERENCE VIDEO block: "From the reference
  video take ONLY the motion: [the motion]. Ignore everything else in it: [its setting]."
  Say in SUBJECT that the hand is on the part the whole time it moves.
- A feature that moves (telescoping, folding): shoot it side-on, the product travelling
  straight across the frame, hands only. Toward or away from the lens it comes back short
  and bent.
- The keyword's thing is not readable in the first second: move it to the first sentence
  of SUBJECT and start the camera closer.
- Subject under the title: set `place` and, if needed, `title_scale` in plan.json (free), or
  restate COMPOSITION and regenerate.
