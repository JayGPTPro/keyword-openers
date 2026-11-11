---
name: keyword-openers
description: One finished product video in, one version per keyword out. Replaces only the picture of the first seconds with a scene that matches a search keyword, puts the keyword on screen, and keeps the video's own soundtrack untouched, so each version is the same length and never sounds like two clips glued together. With the Genrupt MCP connected it writes the opening scenes, generates them (about 5 seconds each), swaps them in, checks every file and builds a review page. Use when a seller has a product video and wants a version per keyword for Sponsored Brands video or any keyword-targeted video ad. Triggers: "keyword openers", "a video per keyword", "video for each keyword", "match my video to my keywords", "change the opening of my video", "PPC video variants", "sponsored brands video per keyword", "/keyword-openers". NOT for making the full product video itself: the seller brings a finished video.
---

# Keyword openers

A shopper who searched "hot dog roasting sticks" and a shopper who searched "vegetable
roasting sticks" get the same video today, and it opens on a marshmallow. This skill gives
each of them an opening that shows what they typed.

**What it changes:** the picture of the first 2 to 6 seconds, and a title with the keyword.
**What it never changes:** the soundtrack, the length, and everything after the first cut.

Sponsored Brands video starts without sound, so the first picture and the words on it are
what the shopper actually gets. That is why the opening is the part worth matching.

## What the seller brings

1. A finished product video (mp4 or mov). 16:9 or 9:16.
2. The keywords, 3 to 10. If they do not have a list, offer to pick: read the listing and
   propose keywords that name a different USE, FOOD, PERSON or PLACE (those change the
   picture). Skip keywords that only reorder the same words; they would get the same scene.
3. The ASIN, so the opening scenes show the real product.

Ask for all three in ONE message. If something is missing, ask once more, then go on.

## Step 1: read the video

```bash
python3 scripts/openers.py inspect "<video>" "<workdir>" --keywords "kw one; kw two; kw three"
```

`<workdir>` is a new folder next to the video, named `keyword-openers`. This writes
`inspect.json`, `plan.json`, and two contact sheets.

**Open `opening-sheet.jpg` and look at it.** The tiles marked REPLACED are what will be
gone. If a logo, a price, a claim or burned-in text sits there, tell the seller before
going on, and offer the earlier cut from `cuts_first_20s` (set `"window"` in `plan.json`).

**Open `look-sheet.jpg` too.** You are about to write scenes that must look like they were
shot for this video: same time of day, same light, same kind of people, same lens feel.

If `notes` in `inspect.json` is not empty, read the notes to the seller as they are.

## Step 2: write one opening scene per keyword

Follow `references/prompt-recipe.md` exactly. One prompt per keyword, each a single shot of
`opener_seconds_to_generate` seconds. Show the seller the scenes as one short line each
("hot dog roasting sticks: a dad and his son holding two hot dogs over the same campfire")
and move on unless they object. Do not paste the full prompts unless asked.

## Step 3: price, then generate

Product reference images: call `scrape_video_reference_images_from_asin` with the ASIN and
wait for the image URLs. Use the first four.

**A keyword that names a moving feature** (extendable, foldable, a lid that opens) needs a
motion reference, or the model invents the mechanism: the first extendable opening made
here grew by itself, like magic. Ask the seller for a short clip of the feature being used
(a customer review video from the listing is ideal, 3 to 8 seconds, at least 300 px tall).
Upload it with the `create_reference_asset_upload` capability (find it with
`search_capabilities`, PUT the file to the URL it returns) and pass the `assetUrl` in
`seedanceReferenceVideoUrls`. In the prompt say what to take from the clip (the motion)
and what to ignore (its table, its light, its other objects). A reference video adds to
the price, so include it in the price check.

Price before anything runs. Call `get_credit_balance_and_costs` with a `video_generation`
preset (model `seedance_2_5_reference`, the resolution nearest the video's own, the opener
length, `videoCount` = number of keywords). Never quote a price from memory. Then say one
line and wait for a yes:

> "5 openings, 5 seconds each, Seedance 2.5 at 720p: [the number the price call returned] credits. Go?"

If the seller wants it cheaper, price `seedance_2_mini_reference` and offer that. A draft
at 480p is fine for judging a scene and too soft for an ad on a 1080p video.

Then one `generate_video` call per keyword, all sent together:

- `modelType: "fal_seedance"`, `seedanceModel`, `seedanceMode: "reference_to_video"`
- `seedanceReferenceImageUrls`: the product images
- `seedanceDuration`: `opener_seconds_to_generate`
- `seedanceAspectRatio`: `aspect` from `inspect.json`
- `seedanceResolution`: as priced
- `asin`: the ASIN (the project is created or reused from it)
- `promptEnhancement: "skip"` (the recipe already wrote the final prompt)
- `sceneTitle`: the keyword

Wait with `wait_for_operation` / `get_video_generation_result`. Download each finished clip
to the path its row in `plan.json` names:

```bash
curl -L -s -o "<workdir>/openers/<slug>.mp4" "<video url>"
```

A generation that fails or is refused: report it in one line and keep going with the rest.
Do not retry more than once without asking; a retry costs the same again.

**No Genrupt?** The skill still works. The seller drops any clip (filmed, stock, another
tool) at the path in `plan.json` and you go straight to step 4.

## Step 4: build every version

```bash
python3 scripts/openers.py build "<workdir>/plan.json"
```

Seconds per version, no credits. For each keyword it swaps the opening picture, draws the
title, and checks the written file: same length as the original, soundtrack identical bit
for bit, the rest of the picture untouched, the opening actually new.

Then **look at every `out/check/<slug>-seam.jpg`**. You are checking three things the
script cannot: the product in the new scene is the seller's product (shape, colour, count),
the title is readable and not sitting on a face or on the thing the keyword names, and the jump from "last
new frame" to "first original frame" reads as a normal cut. A scene that fails gets
regenerated with a corrected prompt (ask first, it costs credits). A title in a bad spot is
free to fix: set `place` or `style` in `plan.json` and build again.

## Step 5: hand over

Open `out/index.html` for the seller. Tell them, in this order:

1. How many versions are ready and where the folder is.
2. Anything you saw on a seam sheet that they should look at.
3. How to use them: `references/amazon-upload.md` (one ad group per keyword, each with its
   own version).

## plan.json

```json
{
  "video": "/path/to/video.mp4",
  "window": 3.875,
  "style": "pop",
  "font": "bold",
  "accent": "CD763C",
  "title": true,
  "opener_audio": "off",
  "variants": [
    {"keyword": "hot dog roasting sticks", "opener": "openers/hot-dog-roasting-sticks.mp4"}
  ]
}
```

- `window`: seconds of picture to replace. `inspect` picks the video's own cut nearest 4
  seconds. Change it only to another value from `cuts_first_20s`.
- `style`: how the keyword is set on screen.
  - `pop` (default): big capitals. The words that make this keyword different from the
    others land on a highlighter bar that wipes in; the rest pop in word by word. Built
    for a small, silent tile in search results.
  - `sticker`: the keyword on a tilted white search sticker that stamps in, the different
    words marked.
  - `kinetic`, `line`, `search`: quiet lower-third titles, for a brand that wants calm.
- `punch`: with `pop` and `sticker` the picture cuts to a 1.15x tighter frame on the beat
  the title lands. `false` turns it off.
- `place` (`pop` and `sticker` only): `auto` (default) puts the title in the calmer band of
  the shot, top or bottom, so it does not cover the subject. `top` or `bottom` forces it.
  The three quiet styles always sit at the bottom.
- `font`: `bold`, `round`, `serif`, `clean`. Match the type already in the video.
- `accent`: taken from the video's own colours. Override with the brand colour if known.
- `title`: `false` for no words on screen.
- `opener_audio`: `"off"` keeps the soundtrack bit for bit. A number such as `-18` folds
  the new scene's own sound in under it at that many dB.
- `take`: an opener is usually a little longer than the window. `end` (default) keeps
  its last seconds, where the scene has settled. `start` keeps its first seconds, for a
  scene whose action begins at once (a stick extending, a lid opening).
- Several takes of one keyword: repeat the variant with the same `keyword`, a different
  `opener` and a `"label"` (`"A"`, `"B"`). Each builds to its own file and card, so the
  seller picks by looking. Offer a second take when a keyword matters; say what it costs.
- A variant may carry `"title_text"` when the words on screen should differ from the
  keyword, `"take"`, `"emphasis"` (the words to mark; by default the words the keywords do not
  share, so "hot dog" in "hot dog roasting sticks"), `"place"`, and its own `"window"`.

## When something is off

`build` checks plan.json first and says in words what to fix. A keyword in letters the
built-in fonts cannot draw (Hebrew, Chinese, Arabic) fails with that sentence: give the
variant a `"title_text"` in Latin letters, or set `"title": false`. Emoji are dropped from
the title. A keyword of more than 5 words is drawn small; give it a shorter `"title_text"`.
A video with no cut between 2 and 6 seconds gets a short dissolve instead of a cut.

## Rules

- Never lengthen the video and never touch its soundtrack. If a request needs either, it
  is a different job; say so.
- Never invent a product feature in a scene. The scene shows the keyword's use with the
  product as it is.
- People in a new scene should match the people in the video when the video has people.
- One paid generation per keyword unless the seller approves another.
