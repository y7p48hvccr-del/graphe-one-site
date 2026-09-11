# ScriptureStudy Pro™ — Lowering the iOS Deployment Target to 18.0

**Feasibility brief and working plan**
**Date:** 2026-09-11
**App:** ScriptureStudy Pro™ (macOS and iPadOS)
**Proposal:** iOS/iPadOS floor 26.5 → **18.0**. macOS floor stays at **26**.

---

## 0. How to use this document

This is a handover brief for a fresh working session. It separates what has been **verified** from what has been **claimed but not yet proven**, because an earlier assessment of this same question produced a confidently wrong 8–14 week estimate based on code that does not exist in the project.

**Rule for this piece of work: no claim is accepted without the command output that demonstrates it.** Section 3 lists the checks to run first.

---

## 1. Decision and rationale

Lower the iOS/iPadOS deployment target from 26.5 to 18.0. Leave macOS at 26.

**Why 18.0 and not 17.6.** iOS 17 and iOS 18 support identical hardware — iPhone XS/XR and later in both cases — so 18.0 gives exactly the same device reach. But 18.0 additionally clears `TranslationSession.Configuration`, which is an iOS 18.0 API and would need its own availability gate at any 17.x floor. Targeting 17.6 is strictly worse than 18.0 for no compensating benefit.

**Why lower it at all.** Apple's published App Store device-support figures, measured 7 June 2026:

| Platform | On version 26 | Not on version 26 |
|---|---|---|
| iPhone — all devices | 79% | **21%** |
| iPad — all devices | 68% | **32%** |

This app is macOS and iPadOS. Roughly **a third of iPads transacting on the App Store cannot run it** at the current floor. Separately, iOS 26 requires iPhone 11 or later — it dropped the XS, XS Max and XR — so part of that excluded group is locked out by hardware and cannot upgrade at all.

Verify current figures at https://developer.apple.com/support/app-store/ before relying on these; they are three months old, and if iOS 27 has shipped the relevant metric becomes the share on 26-or-later.

**Why macOS stays at 26.** The app was built for Apple Silicon from the M1 onward. macOS has no 17.6 equivalent and nothing below 26 is in scope. Deployment targets are per-platform, so this split is a normal configuration, not a compromise.

---

## 2. Established findings

From a grep audit of the codebase:

- **No Liquid Glass APIs are used anywhere.** No `.glassEffect()`, no `GlassEffect` types, no iOS 26-only view modifiers. The Liquid Glass appearance on iOS 26 is applied automatically by the system to standard SwiftUI controls when building against the iOS 26 SDK. It is not called by this code.
- **Consequence:** lowering the deployment target does not remove Liquid Glass on iOS 26 devices, and requires no fallback UI. iOS 26 devices get Liquid Glass; iOS 18–25 devices get the standard pre-26 appearance. There is no dual code path.
- **iOS 17-era APIs found** — `.scrollPosition(id:)`, `.keyframeAnimator` — are both below an 18.0 floor and need nothing.
- **`TranslationSession.Configuration`** (`ModuleCopyrightSheet.swift:28`) requires iOS 18.0 and is satisfied by the new floor. No gate needed.

*(Note: an earlier explanation of the Translation point claimed "17.6 is below 17.4". That is arithmetically false. The conclusion is correct for a different reason — the Configuration API is iOS 18.0, not 17.4 — but the reasoning should not be reused.)*

---

## 3. Verification to run before any code changes

Run these and keep the output. If any result contradicts §2, stop and re-scope.

```bash
# 1. Liquid Glass / iOS 26 view APIs — expect zero hits
grep -rn "glassEffect\|GlassEffect\|glassBackgroundEffect\|scrollEdgeEffect\|tabBarMinimizeBehavior\|backgroundExtensionEffect" --include=*.swift .

# 2. Every FoundationModels reference
grep -rn "FoundationModels\|SystemLanguageModel\|LanguageModelSession\|@Generable\|@Guide" --include=*.swift .

# 3. Every existing availability annotation, to see what is already gated
grep -rn "@available\|#available" --include=*.swift .

# 4. Current deployment targets
grep -n "IPHONEOS_DEPLOYMENT_TARGET\|MACOSX_DEPLOYMENT_TARGET" *.xcodeproj/project.pbxproj | sort -u

# 5. Other iOS 19–25 era APIs worth ruling out
grep -rn "@Entry\|MeshGradient\|onScrollGeometryChange\|onScrollVisibilityChange\|TabView(role:\|AttributedTextSelection\|RichTextEditor\|SpeechAnalyzer\|WebView(" --include=*.swift .
```

**The compiler is the real audit.** Grep finds what you thought to look for. After making the deployment target change, build and let the compiler enumerate every availability failure. That list is exhaustive and cannot be wrong. Treat greps as a sanity check, not as the audit.

---

## 4. The work

### 4.1 Deployment target — one setting

`IPHONEOS_DEPLOYMENT_TARGET` → `18.0`, across every build configuration for the app target and both test targets. Leave `MACOSX_DEPLOYMENT_TARGET` at 26.

Do this **first**, then build, and work from the compiler's error list.

### 4.2 `FoundationModelsService` in `OllamaService.swift`

The only known code change. The blocker is the stored property at line 464:

```swift
private let model = SystemLanguageModel.default
```

A stored property whose *type* is iOS 26-only cannot exist in a class available from iOS 18. The type must not appear in the class's stored storage at all.

**Do not mark the whole class `@available(iOS 26, *)`.** That cascades into every one of the ten-plus call sites in `BrianView`, `SettingsSections`, `PDFReaderView`, `EPUBReaderView` and elsewhere, each of which would then need its own guard. The whole point is to keep those untouched.

**Pattern to use** — keep the class available at 18, push the iOS 26 types behind guards internally:

```swift
import Foundation
import FoundationModels

final class FoundationModelsService {
    static let shared = FoundationModelsService()
    private init() {}

    // No stored property of an iOS 26-only type.

    /// Computed, not stored — an @available annotation is legal here.
    @available(iOS 26, macOS 26, *)
    private var model: SystemLanguageModel {
        SystemLanguageModel.default
    }

    /// Callable from anywhere, at any OS version. False below 26.
    var isAvailable: Bool {
        guard #available(iOS 26, macOS 26, *) else { return false }
        return /* keep whatever availability check the current implementation uses */
    }

    func respond(to prompt: String) async throws -> String {
        guard #available(iOS 26, macOS 26, *) else {
            throw FoundationModelsError.unavailable
        }
        // existing implementation, using `model`
    }
}
```

Two points on this sketch:

- The exact availability check inside `isAvailable` should be **whatever the current working implementation already does** — don't invent a new one from this outline.
- Every method that touches `model` needs the same `guard #available` and a sensible failure for older systems. The call sites read `isAvailable` first, so in practice they should never hit the throw, but it must be there.

**Expected behaviour after the change:** on iOS 18–25, `isAvailable` returns false, the Apple Intelligence route is silently unavailable, and the Claude / OpenAI / Gemini routes are unaffected.

### 4.3 Weak linking — the step most likely to be missed

Swift availability gating controls what the **compiler** accepts. It says nothing about how the framework is **linked**.

If `FoundationModels.framework` is linked as Required rather than Optional, the app will fail at launch on every iOS 18–25 device with a dyld "Library not loaded" error — **before any `#available` check ever executes**. Perfectly gated code, instant crash.

Xcode usually weak-links system frameworks automatically once the deployment target falls below their availability, but verify rather than assume:

1. Build Phases → Link Binary With Libraries → `FoundationModels.framework` should be **Optional**.
2. Confirm on the built binary:

```bash
otool -l "<path to .app>/ScriptureStudy Pro" | grep -B1 -A3 LC_LOAD_WEAK_DYLIB | grep -i foundationmodels
```

A hit under `LC_LOAD_WEAK_DYLIB` is correct. Appearing under `LC_LOAD_DYLIB` instead is the crash condition.

---

## 5. Known risks

**The `@available` cascade.** If anything other than `FoundationModelsService` turns out to hold an iOS 26-only type in storage, the annotation propagates to its owners — view models, environment objects, initialisers. Not difficult, but it is where a "few hours" estimate typically grows. The compiler will show the full extent immediately after §4.1.

**Visual regression on iOS 18–25.** The app has only ever been seen with the iOS 26 appearance applied. Layouts tuned against iOS 26's navigation chrome, safe areas and spacing may sit subtly wrong under the older look. This is design QA rather than engineering, it is currently budgeted at zero, and it is the most likely source of unexpected work.

**Compiling is not launching.** A clean build proves the availability annotations are right. Only a launch on an iOS 18 simulator proves the linking is.

---

## 6. Acceptance criteria

1. Clean build at `IPHONEOS_DEPLOYMENT_TARGET = 18.0`, no availability errors or warnings.
2. Launches on an **iOS 18 simulator** without a dyld error.
3. On iOS 18: Brian view, Settings, PDF reader and EPUB reader all open. Apple Intelligence options are absent or disabled; Claude / OpenAI / Gemini routes work.
4. On iOS 26: Apple Intelligence works as before, and Liquid Glass appearance is unchanged.
5. macOS build unaffected — still targeting 26, no behavioural change.
6. Visual pass on iOS 18 across the main screens, with any layout defects logged.

---

## 7. Out of scope

- Any change to the macOS deployment target
- Any Liquid Glass fallback design — none is required
- Support below iOS 18.0

---

## 8. Open question

Was the API audit run across **all** versions between 18 and 26, or only for Liquid Glass and FoundationModels? The earlier assessment admitted no exhaustive sweep had been done and budgeted 1–3 weeks for what it might find; that caveat then disappeared without being addressed. Grep #5 in §3 partially covers this, but the compiler pass in §4.1 is what settles it definitively.

---

## Sources

- Apple Developer — App Store device support statistics: https://developer.apple.com/support/app-store/
- iOS 26 device compatibility (iPhone 11 and later; XS / XS Max / XR unsupported): https://fone.tips/ios-26-supported-devices/
