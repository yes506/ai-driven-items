# Language skeletons

Per-language abstraction kind, file layout, empty-method convention, and
validation command.

## Selection

`detect_language_stack.sh` returns `language` based on root build files:

| Build file present | Language |
|---|---|
| `pom.xml` | java (Maven) |
| `build.gradle` or `build.gradle.kts` | java (Gradle) |
| `pyproject.toml`, `requirements.txt`, `Pipfile` | python |
| `package.json` + `tsconfig.json` | typescript |
| `package.json` (no `tsconfig.json`) | javascript |
| `go.mod` | go |
| `Cargo.toml` | rust |
| (none) | unknown |

**If `unknown`**: ask the user
"What language? (java/python/typescript/go/rust/other)" and capture as
`LANGUAGE_STACK`. For "other", refuse — this skill's tier-1 support
stops at the listed five. Defer to a follow-up task.

**If `javascript`** (no tsconfig): ask the user "Treat as TypeScript
(recommended; we'll generate `interface` declarations and require
`tsconfig.json`) or refuse?" — there is no first-class skeleton
abstraction for plain JS, since `interface` is a TypeScript-only
construct.

## Per-language conventions

### Java

- **Abstraction kind**: `interface`
- **File layout**: one `.java` per interface, in the package directory
- **Empty method**: just the signature; the interface body is
  implicit-abstract
- **Validation**: `./gradlew compileJava` (Gradle) or `mvn compile`
  (Maven)
- **Docstring format**: Javadoc — see
  [docstring-schema.md](docstring-schema.md)

### Python

- **Abstraction kind**: `typing.Protocol` (preferred for structural
  typing) or `abc.ABC` (when runtime `isinstance` checks are needed)
- **File layout**: one `.py` per interface, OR a single `interfaces.py`
  per package when the package has many small interfaces
- **Empty method**: signature ending in `...` (Ellipsis literal) inside
  a `Protocol`; or `@abstractmethod` decorator + `pass` body in `ABC`
- **Validation**: `mypy --strict <package>` or `pyright`
- **Docstring format**: PEP 257 with structured sections — see
  [docstring-schema.md](docstring-schema.md)

### TypeScript

- **Abstraction kind**: `interface` (preferred for pure shapes) or
  `abstract class` (when needed for instantiation control or shared
  helpers)
- **File layout**: one `.ts` per interface, OR `interfaces/index.ts`
  re-exporting per package
- **Empty method**: signature only (interfaces have no body); or
  `abstract methodName(...): ReturnType` in an abstract class
- **Validation**: `tsc --noEmit`
- **Docstring format**: TSDoc — see
  [docstring-schema.md](docstring-schema.md)

### Go

- **Abstraction kind**: `interface`
- **File layout**: one `.go` per interface, package matches directory
- **Empty method**: just the signature; interface body has no
  implementation slot
- **Validation**: `go build ./...` (will fail if interfaces reference
  unresolved types)
- **Docstring format**: godoc preceding doc-comment — see
  [docstring-schema.md](docstring-schema.md)

### Rust

- **Abstraction kind**: `trait`
- **File layout**: one `.rs` per trait, or `traits.rs` per module
- **Empty method**: `fn methodName(&self, ...) -> ReturnType;` with
  semicolon, no body
- **Validation**: `cargo check`
- **Docstring format**: rustdoc with `///` — see
  [docstring-schema.md](docstring-schema.md)

## Cross-language rule: NO implementation

The skeleton is interface-only. **No method bodies.**

- No `default` methods in Java interfaces
- No `@property`-with-getter in Python `Protocol` classes
- No TS `static` helper bodies in interfaces (use abstract class only
  if the body can't be avoided, and flag it)
- No Go embedding-with-default (embed only other interfaces, not types)
- No Rust `default fn { ... }` blocks in traits

If a language idiom requires a non-interface helper (e.g., a Java
`enum`, a Python `@dataclass` for a value object, a TS `type` alias),
generate it but record it in `.architect-state.json`'s `value_objects`
field separately so the self-verification rubric distinguishes it from
the interface count.

## Compile/type-check failure handling

If Phase 6's command fails:

1. Capture the error output verbatim
2. Identify the failing file and line
3. Surface to user with: "Phase 6 validation failed at `<file>:<line>`.
   Excerpt: `<output>`. Fix the skeleton or revise the decomposition?"
4. Do NOT auto-fix
5. Do NOT prune the worktree
6. Update `.architect-state.json` to `validation_status: failed` and
   leave `phase_completed` at its previous value (`skeleton_written`)
   so resume returns to Phase 6
