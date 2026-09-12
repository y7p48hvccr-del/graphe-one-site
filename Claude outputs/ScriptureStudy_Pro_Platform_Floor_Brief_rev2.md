# ScriptureStudy Pro™ — Lowering the Platform Floors

**Revision 2 — working record and remaining sign-off**
**Date:** 2026-09-11
**App:** ScriptureStudy Pro™ (macOS and iPadOS)
**Branch:** `deployment-target/ios18-macos15`, branched from `main` at `9841949`

| Setting | Was | Now | Note |
|---|---|---|---|
| `IPHONEOS_DEPLOYMENT_TARGET` | 26.0 | **18.0** | changed |
| `MACOSX_DEPLOYMENT_TARGET` | 26.0 | **15.0** | changed |
| `ARCHS` | *(unset)* | *(unset)* | **no change needed** — see §4.1 |

Supersedes revision 1 and the earlier iOS-only brief. Four claims in those documents were wrong; §4 records them so they are not reintroduced.

---

## 0. Status at a glance

**Done and evidenced:** deployment targets changed, `FoundationModelsService` gated, clean build, weak linking confirmed in both architecture slices.

**Outstanding:** three runtime smoke tests, all requiring hardware or a VM. §5.

**Rule carried forward from revision 1:** no claim is accepted without the command output or primary source that demonstrates it. That rule has now caught four errors, one of them in this document's own earlier revision.

---

## 1. What changed, and why

### 1.1 iOS / iPadOS 26.0 → 18.0

Apple's App Store device-support figures, measured 7 June 2026:

| Platform | On version 26 | Not on version 26 |
|---|---|---|
| iPhone — all devices | 79% | **21%** |
| iPad — all devices | 68% | **32%** |

This app ships on iPadOS, the weaker platform. Roughly a third of iPads transacting on the App Store could not run it at the old floor. Separately, iOS 26 requires iPhone 11 or later — it dropped the iPhone XS, XS Max and XR — so part of that group is excluded by hardware and cannot upgrade at any price.

**Why 18.0 and not 17.x:** iOS 17 and iOS 18 support identical hardware (iPhone XS/XR and later), so 18.0 gives the same reach while clearing `TranslationSession.Configuration` (iOS 18.0) and `onScrollGeometryChange` (iOS 18.0 — see §4.4). 17.x would be strictly worse.

*Re-check figures at https://developer.apple.com/support/app-store/ before quoting them; they are three months old.*

### 1.2 macOS 26.0 → 15.0

macOS 15 Sequoia supports Intel Macs; macOS 26 Tahoe supports only a small handful and is the final macOS to support Intel at all. The Intel models Sequoia supports:

- MacBook Pro 13-inch and 15-inch (2018); 13-inch, 15-inch and 16-inch (2019); 13-inch four-port (2020)
- MacBook Air Retina 13-inch (2020)
- iMac Retina 5K 27-inch (2019, 2020); Retina 4K 21.5-inch (2019)
- iMac Pro (2017)
- Mac mini (2018)
- Mac Pro (2019)

**Why macOS 15 and not 14:** Sequoia already reaches 2017–2018 hardware, and both `TranslationSession.Configuration` and `onScrollGeometryChange` are satisfied at 15.0. macOS 14 adds little reach and more API surface.

**Note on sourcing:** automated summaries of Apple's compatibility pages were fetched twice while preparing revision 1, and both concluded "no Intel Macs are supported" while listing Intel machines in the same output. The list above is read from Apple's page directly. Verify at https://support.apple.com/en-us/120282.

### 1.3 Market context

IDC's 2026 memory-shortage analysis forecasts smartphone ASPs up 3–8%, PC ASPs up 4–6% with vendors signalling 15–20% hikes, and market contractions of 2.9–5.2% and 4.9–8.9% respectively. It states that *"longer replacement cycles are likely to occur in markets with rising costs causing lower purchasing power."*

Version-share projections assume the old-OS tail decays at historical rates. If device prices rise and replacement cycles stretch through 2026–27, it decays more slowly, and the 21% / 32% figures behave as a floor rather than a peak.

### 1.4 How the old floors came to exist

The deployment targets were **not present in `project.pbxproj` at all** until commit `9841949` ("Add debug Paywall preview; set iOS target"), where both were set to 26.0 as a side-effect of paywall work by accepting Xcode's suggested defaults. Before that, Xcode used SDK defaults.

There was never a deliberate decision to exclude Intel or older OS versions. An assessment recommending against this change at 8–14 weeks was, in effect, defending a value nobody chose.

---

## 2. Completed work

### 2.1 Deployment targets

`IPHONEOS_DEPLOYMENT_TARGET` → `18.0`, `MACOSX_DEPLOYMENT_TARGET` → `15.0`, across all build configurations for the app target and both test targets. The test targets' `MACOSX_DEPLOYMENT_TARGET = 13.0` was left as found; the compiler did not require a change.

### 2.2 `FoundationModelsService` — commit `a02e9da`

`SystemLanguageModel` is an iOS 26 / macOS 26 type, and a stored property of that type cannot exist on a class available from iOS 18 / macOS 15. The class was kept available at the new floors and the gated type pushed inside:

- Stored property (line 464) → computed property annotated `@available(iOS 26, macOS 26, *)`
- `checkAvailability()` (489) — `#available` guard
- `availabilityReason` (502) — `#available` guard
- `complete()` (523) — `#available` guard around `LanguageModelSession`
- `sendChatStreaming()` (531) — same
- Added a `FoundationModelsUnavailableError` type for the failure path

The class was **not** marked `@available` as a whole, which would have cascaded into all call sites in `BrianView`, `SettingsSections`, `PDFReaderView` and `EPUBReaderView`. All external callers use `isAvailable`, `checkAvailability()`, `complete()` and `sendChatStreaming()` and touch no OS-specific types, so nothing outside `OllamaService.swift` changed.

Every annotation names **both** platforms. An iOS-only annotation would have to be redone for macOS.

Behaviour below the floor: `isAvailable` returns false, Apple Intelligence is silently absent, Claude / OpenAI / Gemini routes unaffected.

### 2.3 Weak linking — verified

Availability gating governs what the compiler accepts; it says nothing about linking. A Required link to `FoundationModels.framework` would crash at launch on every iOS 18–25 / macOS 15–25 system before any `#available` check ran.

Confirmed on the **Release** build, per slice:

```bash
lipo -info "<Release .app>/Contents/MacOS/ScriptureStudy Pro"
otool -arch x86_64 -l "<...>" | grep -A3 LC_LOAD_WEAK_DYLIB | grep -i foundationmodels
otool -arch arm64  -l "<...>" | grep -A3 LC_LOAD_WEAK_DYLIB | grep -i foundationmodels
```

`LC_LOAD_WEAK_DYLIB` present in **both** arm64 and x86_64. Load commands are per-slice in a fat binary, so `-arch` is what makes the answer specific — checking without it is ambiguous, and a Debug build is the wrong artefact because Debug uses dylib injection and is not what ships.

The iOS side needs no separate check: the iOS 18 simulator runtime contains no FoundationModels, so a launch there tests it directly.

### 2.4 Verification findings

- **No Liquid Glass APIs anywhere.** The iOS/macOS 26 appearance is applied by the system to standard SwiftUI controls when building against the 26 SDK. Lowering the floor does not remove it on 26 devices, and no fallback UI is required.
- **Zero pre-existing `@available` / `#available` annotations** in the app. Clean slate.
- **`onScrollGeometryChange`** at `LocalBibleView.swift:1218` — iOS 18.0 / macOS 15.0. Satisfied, exactly at the floor. See §4.4.
- **No Accelerate, Metal, CoreML, MLModel or BNNS calls** in app code.
- **All SPM dependencies clear.** No binary targets; all pure source, so SPM builds whatever slices are requested. Declared minimums all below the new floors: ZIPFoundation macOS 10.11 / iOS 9; BigInt macOS 10.13 / iOS 12; swift-nio-ssh macOS 10.15 / iOS 13; Citadel macOS 14 / iOS 17 (closest, still clear).

---

## 3. Build result

Clean build at iOS 18.0 / macOS 15.0. No availability errors or warnings beyond those fixed in §2.2. No linker errors. No architecture-branch errors — see §4.2 for why none were expected once the real state was understood.

---

## 4. Corrections — claims that proved wrong

Recorded so they are not reintroduced. Three came from the original engineering assessment or its successor; one came from this brief's own earlier revision.

### 4.1 "`ARCHS` must be changed to produce a universal binary"

**Wrong.** `project.pbxproj` contains no explicit `ARCHS` or `EXCLUDED_ARCHS`, so the project inherits the default. In Xcode 26, `ARCHS_STANDARD` for macOS still includes x86_64:

```
Release:  ARCHS = arm64 x86_64   ONLY_ACTIVE_ARCH = NO
Debug:    ARCHS = arm64          ONLY_ACTIVE_ARCH = YES
```

Release has been building a universal binary all along. **The `ARCHS` commit was dropped as a no-op.** Intel was excluded solely by the deployment target.

*(Also noted: adding an explicit `ARCHS` would not have slowed Debug builds, because `ONLY_ACTIVE_ARCH = YES` takes precedence in Debug regardless.)*

### 4.2 "The `#if !arch(arm64)` branches have never been parsed"

**Wrong**, and it was this document's claim in revision 1. The reasoning was that a preprocessor branch is invisible to the type checker when `ARCHS` is arm64-only — correct in principle, but it assumed an `ARCHS` value that was never checked. Since Release builds both slices, those branches have been compiled on every Release build and the compiler has been passing them.

Compilation risk is therefore nil. **The residual Intel risk is runtime behaviour only** — see §6.

### 4.3 "macOS 15 and macOS 26 have the same hardware ceiling; both require Apple Silicon"

**Wrong.** macOS 15 supports Intel Macs back to 2017–2018 (§1.2). This claim, had it stood, would have closed off the entire Intel case.

A related claim that macOS 15 supports "2015 and later iMac, 2013 and later Mac Pro" was also wrong — those models top out several releases earlier.

### 4.4 "`onScrollGeometryChange` is iOS 17.0 / macOS 14.0"

**Wrong.** It arrived at WWDC24: **iOS 18.0 / macOS 15.0**. The iOS 17 scroll APIs were `.scrollPosition(id:)`, `.scrollTargetBehavior` and `.scrollTransition`.

The conclusion was unaffected — it is satisfied at the new floors — but it sits *exactly* on them. **If anyone revisits lowering to iOS 17 or macOS 14, `LocalBibleView.swift:1218` becomes a blocker requiring a gate.** Recorded as 17/14 it would have looked safe when it is not.

---

## 5. Remaining work — three smoke tests

All require a running system; none can be inferred from a build.

### 5.1 iOS 18 simulator

Download the iOS 18.x runtime first (Xcode → Settings → Components; several GB, not bundled with Xcode 26). Boot, install, launch.

Confirm: no crash at launch — this is the iOS weak-link test, since that runtime has no FoundationModels; Brian, Settings, PDF reader and EPUB reader all open; Apple Intelligence options absent or disabled; Claude / OpenAI / Gemini routes work.

### 5.2 macOS 15 VM

Virtualization.framework runs ARM macOS 12+ on Apple Silicon. VirtualBuddy or UTM from an IPSW. This is the only step with real setup time.

Confirm: launches without a dyld error; the same four screens; the same Apple Intelligence absence; window chrome and toolbar geometry under Sequoia's appearance.

### 5.3 Rosetta — inside the VM, not on the host

Build universal, Get Info on the .app, tick **Open using Rosetta**.

**The distinction matters and should not be skipped.** Running this on the macOS 26 host only proves the Intel slice executes under translation against a 26 runtime. It does not reproduce what an Intel user sees. Running it **inside the macOS 15 VM** tests the Intel code path on the floor being advertised, and that is the run that backs the compatibility claim.

Confirm: launches, reaches the main window, and the `#if !arch(arm64)` paths behave — `ArchitectureDefaults.swift` seeds conservative defaults and the Settings warning banner appears.

---

## 6. Remaining risks

**Intel runtime behaviour.** The arch branches compile, and have done for a long time. Nothing has ever *run* them on Intel hardware. `ArchitectureDefaults.swift` exists specifically to tune performance defaults down on Intel, and those values cannot be validated on translated x86 running on an M1 — Rosetta on Apple Silicon is comfortably faster than a real 2018 Intel Mac. Whether the defaults are sensible, too timid, or not timid enough is unknown until the app runs on real Intel hardware.

**Visual regression.** The app has only ever been seen with the version 26 appearance. On iOS 18–25 and macOS 15–25 the system applies the older look — different window styling, toolbar layout, navigation chrome, safe areas, spacing. This is design QA, currently costed at zero, and remains the most likely source of unexpected work. Log defects; do not fix them in this branch.

**Testing gap.** No Intel hardware is available. The table below is what the M1 covers.

| What | How | Covered |
|---|---|---|
| iOS 18 behaviour and weak linking | iOS 18 simulator | Yes |
| iOS 26 regression | iOS 26 simulator | Yes |
| macOS 15 behaviour and weak linking | macOS 15 VM | Yes |
| macOS 26 regression | the M1 itself | Yes |
| x86_64 slice executes on macOS 15 | Rosetta inside the macOS 15 VM | Close proxy |
| Real Intel hardware on macOS 15 | — | **Not covered** |

If an Intel machine is acquired, a 2018 Mac mini or 2019 13-inch MacBook Pro is the cheap end of what runs Sequoia and a fair proxy for what Intel users have. Wait until the branch merges — there is nothing left that could invalidate the Intel half.

---

## 7. Acceptance criteria

| # | Criterion | Status |
|---|---|---|
| 1 | Clean build at iOS 18.0 / macOS 15.0 | **Done** |
| 2 | `FoundationModels` weak-linked, both slices, Release | **Done** |
| 3 | Universal binary confirmed by `lipo` | **Done** |
| 4 | iOS 18 simulator launches, no dyld error | Outstanding |
| 5 | macOS 15 VM launches, no dyld error | Outstanding |
| 6 | x86_64 slice launches under Rosetta **in the VM** | Outstanding |
| 7 | Below the floors: four main screens open; Apple Intelligence absent; other AI routes work | Outstanding |
| 8 | At version 26: Apple Intelligence unchanged, Liquid Glass unchanged | Outstanding |
| 9 | Visual pass on both lower floors, defects logged not fixed | Outstanding |

---

## 8. Out of scope

- Support below iOS 18.0 or macOS 15.0
- Any Liquid Glass fallback design — none is required
- Fixing visual regressions found at criterion 9
- Supporting OpenCore Legacy Patcher configurations. A universal binary happens to run on many of them, which is free upside, but they are unsupported by Apple. Consider stating in support material that Intel Macs are supported where Apple supports them.

---

## 9. Notes for any future change

- **Do not lower to iOS 17 or macOS 14 without gating `onScrollGeometryChange`** (§4.4).
- **Intel has a finite runway.** macOS 26 is the last macOS supporting Intel; those machines stop receiving OS updates after this cycle. A future Xcode will eventually stop emitting x86_64 at all, at which point `ARCHS_STANDARD` quietly becomes arm64-only and the Intel slice disappears without any project change. Worth re-running `xcodebuild -showBuildSettings` after each major Xcode upgrade.
- **Citadel declares macOS 14 / iOS 17** — the closest dependency to the floor. Re-check it if floors ever move.

---

## Sources

- Apple Developer — App Store device support statistics: https://developer.apple.com/support/app-store/
- macOS Sequoia (15) compatibility — Apple Support: https://support.apple.com/en-us/120282
- macOS Tahoe (26) compatibility — Apple Support: https://support.apple.com/en-us/122867
- iOS 26 device compatibility: https://fone.tips/ios-26-supported-devices/
- `onScrollGeometryChange` introduced in iOS 18: https://augmentedcode.io/2024/07/01/scroll-geometry-and-position-view-modifiers-in-swiftui-on-ios-18/ · https://developer.apple.com/videos/play/wwdc2024/10144/
- IDC — Global memory shortage crisis, 2026 smartphone and PC impact: https://www.idc.com/resource-center/blog/global-memory-shortage-crisis-market-analysis-and-the-potential-impact-on-the-smartphone-and-pc-markets-in-2026/
