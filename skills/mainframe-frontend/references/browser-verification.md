# Browser verification

Do not call a visual or interactive change complete from source inspection, build output, unit tests, DOM snapshots, or screenshots alone. Exercise the actual rendered surface through a browser-capable mechanism as a user would.

Prefer the receiving agent product's native interactive browser when it is available and permitted. During adaptation, identify that native capability from current product documentation and configure only the access required for the receiving project. Do not put product-specific browser names, paths, permissions, or registration in the canonical skill.

If no adequate native browser exists, obtain the responsible user's choice through the current execution path and configure an available substitute such as the project's existing browser harness, Playwright, Browser Use, agent-browser, or another interactive browser. Record the chosen command, URL or contour, startup boundary, permissions, and allowed credentials in the project layer. Do not install or authorize a substitute silently.

An adequate mechanism must be able to open the real route and interact with it: click, type, scroll, use the keyboard, resize or emulate supported viewports, and observe navigation and visible state. It should expose console and runtime failures and verify actual downloads or browser APIs when those are part of the changed contract.

Exercise the changed journey with representative data and every material reachable state. Check normal desktop, a meaningful narrow viewport, reduced height, keyboard and focus behavior, overflow and overlays, supported themes, reduced motion, error recovery, and preservation of drafts or selection where relevant. Wait for the application to settle after resize or navigation before accepting appearance.

Use an authorized local or test contour. Do not spend money, mutate production, alter credentials, or trigger irreversible operations merely for visual proof. Keep simulated data visibly distinct from live runtime evidence.

Capture screenshots when they help demonstrate appearance, but pair them with interaction evidence. Report the route, states, interactions, viewports, console result, downloads or browser APIs exercised, and any limitation. If no adequate browser route can be established, state that visual or interactive acceptance remains unverified rather than claiming completion.
