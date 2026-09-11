# Response to the iOS 17.6 Deployment Target Assessment

**Date:** 2026-09-11
**App:** ScriptureStudy Pro™ (macOS and iPadOS)
**Responding to:** *iOS 17.6 Minimum Deployment Target — Engineering Assessment*, 2026-09-11
**Status:** Requests a revised assessment. Does not overturn the recommendation.

---

## Summary

The assessment recommends keeping the iOS minimum at 26.5, on the basis that the work costs 8–14 weeks and the market expansion is 1–3%.

The engineering half of that argument is sound and is not disputed here. The market half does not survive checking. Apple's own published figures put the excluded share at **21% of iPhones and 32% of iPads**, not 1–3% — and the assessment's claim that iOS 26 and iOS 17 support near-identical hardware is factually incorrect.

The decision may still come out the same way. But it should be made against the real numbers, and against a lower target than 17.6, which is strictly worse than the obvious alternative.

---

## 1. Factual correction: hardware compatibility

The assessment states (§ Market Expansion Analysis):

> "iOS 17 requires iPhone XS or later (2018). iOS 26 also supports iPhone XS and later. The compatible hardware overlap is nearly identical."

This is wrong. **iOS 26 requires iPhone 11 or later (A13 and up).** It dropped the iPhone XS, XS Max and XR. iOS 17 and iOS 18 both support XS/XR and later.

The consequence is material. The assessment's case rests on the premise that everyone gained is someone who *could* upgrade but has chosen not to. In fact, lowering the floor reaches three iPhone models — including the XR, among the best-selling iPhones ever made — that **cannot run iOS 26 at any price**. Those users are locked out by hardware, not by preference.

---

## 2. Factual correction: size of the excluded market

Apple's published App Store device-support statistics, measured **7 June 2026**:

| Platform | On version 26 | **Not on version 26** |
|---|---|---|
| iPhone — all devices | 79% | **21%** |
| iPhone — introduced in last 4 years | 86% | 14% |
| iPad — all devices | 68% | **32%** |
| iPad — introduced in last 4 years | 79% | 21% |

The assessment's figure of 1–3% is out by roughly an order of magnitude.

This matters more for this app than for most, because **ScriptureStudy Pro is an iPadOS app**, and iPad is by far the weaker platform for OS adoption. Close to a third of iPads transacting on the App Store cannot run the app as currently targeted.

**Caveats, stated plainly:** these figures are three months old and adoption will have risen since; if iOS 27 has now shipped, the correct metric becomes the share on 26-or-later; and not every excluded device represents a lost customer, since some users would upgrade to reach the app. The revised assessment should source current figures rather than reuse these.

---

## 3. The proposed target is wrong — it should be iOS 18, not 17.6

iOS 17 and iOS 18 support **identical hardware**: iPhone XS/XR and later in both cases.

Therefore targeting iOS 18 delivers exactly the same device reach as 17.6, while eliminating one of the four problems the assessment identifies. `TranslationSession.Configuration` requires iOS 18; at a 17.6 floor it remains broken and needs its own availability gate and a hidden state for iOS 17 users (§3 of the assessment).

Targeting 17.6 is strictly worse than targeting 18, for no compensating benefit. Whatever else is decided, 17.6 should be taken off the table.

---

## 4. The engineering argument, which stands

The Liquid Glass analysis is the strongest part of the assessment and nothing here undermines it:

- Liquid Glass is the app's visual identity, not a decorative layer
- There is no automatic degradation — a second design has to be designed and written
- The fallback path will be under-tested, because it won't run on the team's own hardware
- Every future feature carries a permanent overhead

For a solo developer this is a serious, open-ended commitment, and it remains a legitimate basis for declining.

For contrast: a sibling app in the same portfolio (Scrib, pure UIKit, no SwiftUI) had its floor lowered from 26.5 to 17 this week by changing one build setting, with no code changes. The difference is entirely attributable to what the UI is built on. The Liquid Glass dependency is the real cost here — not the OS version number.

---

## 5. Questions the revised assessment should answer

**5.1 — How many of the 40–70 affected views are shared, and how many are iOS-only?**
Deployment targets are per-platform, so macOS can stay at 26. But shared SwiftUI views must still compile against the lower iOS floor, so the split only helps to the extent that view code is already platform-specific. This ratio should be measured, not estimated.

**5.2 — Can the branching be centralised into a single modifier?**
This is the most important question, because it is what the 6–10 week estimate rests on. Rather than an `#available` branch in each of 40–70 files, a single custom `ViewModifier` — `.adaptiveGlass()` or similar — could branch internally between `.glassEffect()` and a Materials fallback, and be applied at every call site via mechanical find-and-replace.

If that works, the engineering cost collapses from 40–70 files of bespoke dual-path code to one file plus a mechanical substitution, and the residual work becomes *design* — deciding how the Materials fallback should look — rather than per-view engineering. That is a materially different project.

The assessment asserts "there is no shortcut" without evaluating this approach. It should be prototyped on three or four representative views before the 6–10 week figure is accepted.

**5.3 — What does the audit actually find?**
The assessment concedes no exhaustive API audit has been done (§4) and estimates 1–3 further weeks on unknowns. That is a large band resting on nothing. The audit is 1–2 days and should be completed before any decision, not after.

**5.4 — Is a staged approach available?**
Ship at the current floor now; lower it in a later version once real App Store analytics show where users actually are. This defers the cost without forfeiting the option, and replaces estimates with observed data from the app's own install base.

---

## 6. A note on the closing paragraph

The assessment ends:

> "Third World reach is better served by Android, which is where lower-end budget devices are concentrated — iOS devices in those markets are predominantly second-hand iPhones running recent iOS versions via hand-me-down chains."

No source is offered for any part of this, and the final clause — that second-hand iPhones in those markets run recent iOS versions — is the specific claim most likely to be wrong, since second-hand hand-me-down chains bias *older*, which is the opposite of what is asserted. It should be sourced or removed. As written it reads as a conclusion in search of evidence, and it sits awkwardly in an otherwise careful document.

---

## 7. Requested outcome

1. Drop 17.6 from consideration; evaluate **iOS 18** instead.
2. Re-run the market section against current Apple figures, noting the iPadOS split specifically.
3. Complete the API audit (1–2 days) before the decision, not after.
4. Prototype the centralised `.adaptiveGlass()` modifier on a small sample of views and re-estimate § "Liquid Glass dual-path UI" on that basis.
5. Re-present the decision as a genuine trade-off — cost versus roughly a third of the iPad install base — rather than as a foregone conclusion.

If the revised numbers still favour holding at 26, that conclusion will be well-founded and can be adopted with confidence. The objection is to the reasoning, not to the outcome.

---

## Sources

- Apple Developer — App Store device support statistics (iOS/iPadOS version share, measured 7 June 2026): https://developer.apple.com/support/app-store/
- iOS 26 device compatibility (iPhone XS, XS Max and XR unsupported; iPhone 11 and later required): https://fone.tips/ios-26-supported-devices/
- iOS version support by device — Statista: https://www.statista.com/chart/5824/ios-versions-supported-by-apple/
