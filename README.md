# keyword-openers

A Claude Code skill. One finished product video in, one version per keyword out.

It replaces only the picture of the first few seconds with a scene that matches a search
keyword, puts the keyword on screen, and leaves the video's own soundtrack untouched. Each
version is the same length as the original and lands back on one of the video's own cuts.

## What you need

- Claude Code
- `ffmpeg` (Mac: `brew install ffmpeg`. Windows: `winget install --id Gyan.FFmpeg -e`)
- Python 3 with `numpy` and `Pillow` (Mac: `pip3 install numpy pillow`. Windows:
  `pip install numpy pillow`)
- To have the opening scenes generated for you: the Genrupt MCP connected
  (`claude mcp add --scope user --transport http genrupt https://genrupt.com/api/agent/mcp`).
  Without it, drop your own clips in and the skill does the rest.

## Install

```
npx skills add JayGPTPro/keyword-openers -g
```

The step-by-step setup guide (Claude Code, ffmpeg, Genrupt, first run, Amazon upload) is at
[jaygptpro.com/keyword-openers/guide](https://jaygptpro.com/keyword-openers/guide/).

## Use it

Open Claude Code in the folder that holds your video and say:

```
/keyword-openers my-video.mp4, ASIN B0XXXXXXXX, keywords: hot dog roasting sticks, vegetable roasting sticks, bbq roasting sticks
```

You get `keyword-openers/out/upload/` with one mp4 per keyword, named by the keyword, and
`keyword-openers/out/index.html` to review every version and see which file goes to which
ad group.

## Fonts

The four typefaces in `fonts/` (Archivo Black, Baloo 2, Fraunces, Outfit) are licensed
under the SIL Open Font License 1.1; each license is in `fonts/OFL-*.txt`. Everything else is MIT (`LICENSE`).
