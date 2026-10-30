# DriveScope Immersive Intro Experience Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a cinematic first-person cockpit intro that starts from the supplied image hotspot and transitions into the already-mounted DriveScope homepage without changing its business behavior.

**Architecture:** Keep `App` as the homepage owner and render `DriveScopeIntro` as a sibling fixed overlay. The homepage remains mounted from the first render and receives a reveal class during the intro timeline, while the intro owns its `idle → starting → entered` state, body-scroll lock, normalized cover-crop hotspot positioning, parallax, and GSAP timeline. A small pure layout helper makes the ENGINE START hit area responsive to `object-fit: cover` cropping.

**Tech Stack:** React 19, TypeScript, Vite, Vitest, Testing Library, GSAP, CSS transforms/filters, ResizeObserver.

**Spec:** Current user-provided DriveScope immersive intro implementation brief.

## Global Constraints

- Do not delete, restructure, or change the existing homepage business flow or API calls.
- Use the supplied first-person cockpit image as the intro visual and preserve its 1280×720 composition.
- The ENGINE START hotspot must be a semantic transparent HTML button positioned from normalized source coordinates and remain correct under `object-fit: cover` cropping.
- Use one GSAP timeline for button feedback, cockpit power-up, camera pull-back, homepage reveal, and intro exit.
- Intro states are `idle`, `starting`, and `entered`; repeated clicks must not start a second timeline.
- Lock body scroll while the intro is interactive and restore it after completion.
- Support keyboard activation, `aria-label="Start DriveScope"`, `prefers-reduced-motion`, desktop aspect ratios, and mobile cropping.
- Do not add an API key, sound requirement, ordinary center Start button, direct navigation, or a fake loading screen.

---

### Task 1: Establish the responsive hotspot contract with tests

**Files:**
- Modify: `frontend/package.json`, `frontend/pnpm-lock.yaml`
- Create: `frontend/src/components/intro/introLayout.ts`
- Create: `frontend/src/components/intro/introLayout.test.ts`
- Create: `frontend/src/components/intro/DriveScopeIntro.test.tsx`

**Interfaces:**
- `getCoverHotspotRect(containerWidth, containerHeight, imageWidth, imageHeight, normalizedRect)` returns a pixel rectangle that maps a normalized source rectangle through `object-fit: cover`.
- `DriveScopeIntro` exposes `onReveal?: () => void`, `onComplete?: () => void`, and renders `button[aria-label="Start DriveScope"]`.

- [ ] **Step 1: Add the GSAP dependency without touching homepage code.**

  Run `pnpm add gsap` from `frontend/` and confirm `gsap` is recorded in both package manifests.

- [ ] **Step 2: Write the failing cover-crop test.**

  Assert that a 16:9 source in a portrait container is cropped horizontally and that the normalized ENGINE START rectangle is translated by the crop offset rather than left at a fixed percentage.

- [ ] **Step 3: Write the failing intro interaction tests.**

  Render the not-yet-created component, assert the semantic button and `document.body.style.overflow === 'hidden'`, click twice, and assert `onReveal` can be called only once. Also assert reduced-motion markup remains clickable.

- [ ] **Step 4: Run only these tests and verify the expected RED state.**

  Run `pnpm vitest run src/components/intro/introLayout.test.ts src/components/intro/DriveScopeIntro.test.tsx --configLoader runner` from `frontend/`. Expected failure: the helper/component modules do not yet exist.

---

### Task 2: Build the isolated Intro component and timeline

**Files:**
- Create: `frontend/src/components/intro/DriveScopeIntro.tsx`
- Modify: `frontend/src/components/intro/introLayout.ts`
- Test: `frontend/src/components/intro/DriveScopeIntro.test.tsx`

**Interfaces:**
- `DriveScopeIntro({ onReveal, onComplete }: { onReveal?: () => void; onComplete?: () => void })` owns `idle | starting | entered` and never calls either callback more than once.
- The cockpit media wrapper contains both the `img` and the normalized hotspot so parallax moves them together.

- [ ] **Step 1: Implement the pure cover-crop mapping and hotspot constants.**

  Use the supplied source dimensions `1280 × 720` and a normalized source rectangle around the visible ENGINE START button (`x≈0.61, y≈0.79, width≈0.13, height≈0.15`). Recalculate its viewport rectangle with `ResizeObserver` so resize/orientation changes are covered.

- [ ] **Step 2: Implement idle rendering and body-scroll ownership.**

  Render a full-viewport dark fallback, the cockpit image, a transparent semantic button over the mapped hotspot, a restrained `PRESS TO START` hint, and no ordinary center CTA. Lock body scrolling while idle/starting and restore the previous overflow value after completion/unmount.

- [ ] **Step 3: Implement the GSAP timeline.**

  Use one `gsap.timeline()` with button press feedback, a 1–2px power-up nudge, red-light emphasis, `scale + y + rotateX + borderRadius + boxShadow` camera pull-back, overlapping `onReveal`, then final opacity/blur exit and `onComplete`. Guard the handler when state is not `idle`.

- [ ] **Step 4: Implement parallax with GSAP quick setters/quickTo.**

  Register one pointer listener and update CSS variables or the media wrapper through `requestAnimationFrame`/`quickTo`; cap desktop movement at 8px and rotation below 0.8 degrees. Disable or reduce it for touch and reduced-motion users.

- [ ] **Step 5: Run the focused tests and verify GREEN.**

  Run the same two focused Vitest files. Expected result: all hotspot, semantic-button, scroll-lock, and duplicate-click tests pass.

---

### Task 3: Integrate the intro without changing homepage behavior

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/App.test.tsx`

**Interfaces:**
- `App` mounts its existing `<main>` immediately, adds only an intro visibility class, and renders `<DriveScopeIntro onReveal={...} onComplete={...} />` as a sibling.

- [ ] **Step 1: Add a failing integration assertion.**

  Assert that the homepage controls are present while the intro button is present, and that clicking the start hotspot reveals the homepage class without changing the existing upload/chat API behavior.

- [ ] **Step 2: Integrate the sibling intro layer.**

  Keep the existing status fetch, upload, chat, trace, archive, and result rendering intact. Only add `homepageVisible` state/classes and the Intro component callbacks.

- [ ] **Step 3: Run `App.test.tsx` and confirm the existing agent tests plus the new integration test pass.**

---

### Task 4: Add visual treatment, asset, responsive behavior, and accessibility styles

**Files:**
- Create: `frontend/public/assets/intro-cockpit.jpg`
- Modify: `frontend/src/styles.css`

- [ ] **Step 1: Copy the supplied cockpit image into the public asset path without overwriting existing assets.**

  Copy the supplied attachment to `frontend/public/assets/intro-cockpit.jpg`; keep the original attachment unchanged.

- [ ] **Step 2: Add the Intro visual system.**

  Add dark fallback, cover image positioning, subtle red hotspot ring/pulse, low-key hint fade, perspective scene, and class-based power-up/pull-back states. Keep the DriveScope black/deep-gray/white/red language and avoid neon or game-like decorations.

- [ ] **Step 3: Add homepage reveal and stagger hooks.**

  Animate the existing page from `opacity: 0; transform: scale(1.04) translateY(20px); filter: blur(8px)` to normal when revealed, then use existing structural selectors for a restrained 10–16px, 0.35–0.5s stagger. Do not alter content or API state.

- [ ] **Step 4: Add desktop/mobile/reduced-motion rules.**

  Preserve the supplied image’s 16:9 composition on desktop, tune `object-position` for mobile to keep road, steering wheel, ENGINE START, and the left DriveScope billboard visible, reduce 3D/blur/shadow on small screens, and keep keyboard focus visible without a rectangular visual box.

- [ ] **Step 5: Run frontend type-checking and focused tests.**

  Run `pnpm test -- --run --configLoader runner` and `pnpm run build` from `frontend/` after the styles and asset are wired.

---

### Task 5: Real browser acceptance and regression verification

**Files:**
- Modify: none unless verification finds a concrete defect.

- [ ] **Step 1: Start or reuse the local frontend and verify the page identity.**

  Confirm `http://127.0.0.1:5173/` loads the intended DriveScope page with no framework overlay.

- [ ] **Step 2: Exercise the target interaction.**

  Observe the cockpit intro, hover/focus the ENGINE START hotspot, activate it once, verify the press/power/pull-back sequence, verify the homepage becomes interactive after the overlapping reveal, and click a homepage control afterward.

- [ ] **Step 3: Check responsive and accessibility behavior.**

  Inspect desktop and mobile CSS behavior, verify the hotspot remains tied to the source button under crop rules, test Enter/Space activation, confirm reduced-motion removes the large movement but retains the transition and homepage reveal.

- [ ] **Step 4: Run the complete frontend suite and production build.**

  Record test counts, build output, and any known browser/viewport limitations without treating build success as visual acceptance.
