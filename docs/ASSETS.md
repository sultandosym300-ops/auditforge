# Asset provenance and licenses

- Video and derived poster: [Modern Skyscraper Close-Up Financial District, Pexels](https://www.pexels.com/video/modern-skyscraper-close-up-financial-district-39307168/), downloaded source `https://videos.pexels.com/video-files/39307168/16725711_1080_1920_60fps.mp4`. The self-hosted WebM is a VP9 transcode to 720x1280 at 30fps. Poster is its first frame. Pexels content retains the [Pexels license](https://www.pexels.com/license/). The original user Apple video was used only as a reference and is not redistributed.
- Manrope variable font: self-hosted Google Fonts files, [Manrope](https://fonts.google.com/specimen/Manrope), SIL Open Font License. SF Pro is requested as an installed system font; Apple font files are not redistributed. On systems without SF Pro the explicit fallback is Manrope.
- Lucide icons: lucide-react 0.468.0, ISC license.
- Three.js geometry and document canvas: authored procedural assets, project MIT license. No stock 3D model.
- Pyodide 0.27.7: Mozilla Public License 2.0, packaged runtime includes its upstream components; see the [Pyodide repository](https://github.com/pyodide/pyodide).
- React, GSAP and Vite retain their respective upstream licenses, specified by package-lock.json.

The illustrative document amounts in the presentation are visual examples. Workspace records and reports are generated and evaluated live.

## Revision 1.1 — two distinct video sources

The cinematic closing-media scene now uses [Vibrant Night Skyline of Downtown City](https://www.pexels.com/video/vibrant-night-skyline-of-downtown-city-30747149/), source `https://videos.pexels.com/video-files/30747149/13153068_1440_2560_30fps.mp4`. It is centre-cropped and self-hosted as 1280x800 VP9/WebM; its first frame supplies night-poster.jpg. The earlier blue-building footage appears only in the interaction feature. Each clip appears once; the final CTA uses an authored evidence-path diagram, not repeated stock footage.

## Sharpness revision — original-resolution footage

The current runtime uses `city-hq.webm` (1080×1920, 30fps, VP9 CRF20) from the original 1080×1920 city source, and `night-hq.webm` (2160×1216, 30fps, VP9 CRF20), a native-width centre crop of the publisher’s 2160×3840 original: `https://videos.pexels.com/video-files/30747149/13153069_2160_3840_30fps.mp4`. Neither output is an upscale. The night original is a portrait 4K file; the landscape output is correctly described as 2160×1216, not landscape 4K. Posters are regenerated at the same output dimensions with high JPEG quality. The earlier lower-resolution transcodes are superseded. Full-scene destructive darkening/desaturation was reduced while retaining the text contrast overlay and continuous fade.

Three.js scenes render at a minimum 2× pixel ratio, capped at 3×. Dossier document faces are 1800×2560, with maximum available anisotropic filtering. These are authored textures, not downloaded models. Scroll depth now preserves the source-to-finding order throughout, with no zero-crossing that would reverse occlusion; cursor pose is damped.

The current loops are 10 seconds. The high-quality encodes are trimmed by stream copy, with no additional quality loss, keeping each served media asset below 25 MiB. Superseded lower-quality files are removed from the build.
