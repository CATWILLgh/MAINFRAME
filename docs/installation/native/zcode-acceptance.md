# One ZCode Desktop acceptance pass

Run only when the user explicitly requests native acceptance, in a **new ZCode
Desktop session** opened at this MAINFRAME checkout after the maintained update.
This is not an installation step. Do not launch CLI agents, change settings,
use credentials, or run a model matrix. Keep the app's normal permissions.

1. From the repository root, run exactly
   `python3 -B install.py zcode verify --surface desktop` once. Stop on a
   delivery mismatch. Do not inspect help, retry an incomplete command, or
   reparse the state with ad-hoc scripts; this report already contains the
   delivery counts and limitations.
   The two unsupported full completion contracts, the retained partial
   `mainframe-code-quality` binding, and missing subagent inheritance are documented
   boundaries, not instructions to develop new adapters.
2. Run `python3 -B tests/probes/zcode_desktop_fixture.py`. It creates one private,
   disposable fixture and prints five exact commands. Run each command separately
   through native Bash, without prepending a shell wrapper or changing the paths.
   The apparent `rm` and `mainframe-secret` executables are inert fixture scripts, never
   the real tools. The Git repository is also disposable.
3. Expect `secret_deny`, `destructive_deny`, and `commit_deny` to be denied with
   the corresponding MAINFRAME reason. A model refusing to call a tool, a native
   permission refusal, or a missing executable is **not** hook proof. Expect
   `rg_advice` to execute and deliver the ripgrep correction as model context;
   expect `clean_allow` to execute silently without MAINFRAME advice. Do not
   retry a denied command with a bypass or weaken the installed policy.
4. Report the actual native denial/context for each case. Check that no commit
   was created in the disposable repository. Record missing or contrary outcomes
   as failures, not as success inferred from installed files.
5. Report which MAINFRAME skills and seven roles the native catalog actually
   exposed. Load `mainframe-harness-feedback` through native Skill once, without
   filing a synthetic issue. Catalog presence does not prove role behavior or
   exhaustive skill/command acceptance; keep those claims separate.
6. Use native `Write` or `Edit` on the reported `quality_file` to replace its
   contents with `package fixture` followed by `// TODO: finish behavior`.
   Expect the post-edit mainframe-code-quality advice and a single Stop continuation that
   names the introduced finding. In that continuation, restore the file to only
   `package fixture`; expect completion to proceed. Do not force another turn
   merely to test unavailable-scanner advice.
7. Remove only the exact private fixture returned by the preparation script,
   using Python `shutil.rmtree` after checking its temporary-directory location
   and `mainframe-zcode-acceptance-` prefix. Do not remove user files or old hook
   callbacks. Return one short outcome per check; do not start another campaign.

The user can return this session's identifier for inspection of tool outcomes.
No screenshot or control of the user's screen is required.
