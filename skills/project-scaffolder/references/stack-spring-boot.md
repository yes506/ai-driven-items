# Stack: Spring Boot (Kotlin or Java, Gradle KTS)

## Initialization

Use Spring Initializr CLI or the web UI:

```bash
# CLI (preferred — current stable picked automatically).
# javaVersion intentionally omitted: Spring Initializr defaults to the
# current Spring-Boot-supported LTS at request time. If a specific JDK
# major is required, capture the user's choice in Phase 1 and pass it
# explicitly here (e.g. `-d javaVersion=21`).
curl https://start.spring.io/starter.zip \
  -d type=gradle-project-kotlin \
  -d language=kotlin \
  -d packaging=jar \
  -d dependencies=web,actuator,configuration-processor \
  -o starter.zip
unzip starter.zip -d <project-name> && rm starter.zip
```

Do not hand-roll the Gradle build. Spring Initializr is the canonical source.

## Allowed scaffold additions

- `src/main/kotlin/.../config/AppProperties.kt` — `@ConfigurationProperties` bean
- `src/main/kotlin/.../logging/StructuredLogger.kt` — thin wrapper or no-op
- `src/main/kotlin/.../errors/BaseException.kt` + `GlobalExceptionHandler.kt`
- `src/main/resources/application.yml` — empty top-level + `management.endpoints` for actuator
- Spring Boot Actuator gives `/actuator/health` for free — do not hand-roll a `/health` controller
- `.env.example` (read via `spring.config.import=optional:file:.env[.properties]`)
- `Dockerfile` (eclipse-temurin multi-stage: build → runtime)
- `.github/workflows/ci.yml` — `./gradlew check` (only if user opts in)
- `gradle/libs.versions.toml` (version catalog) — present but with TODOs not pinned versions

## Denied

- `@Entity` classes
- `@RestController` for any business path
- Spring Security configuration with real providers
- JPA / R2DBC repository interfaces beyond a generic base
- Liquibase / Flyway migrations with content (init the tool, leave migrations empty)

## Smoke test

```bash
./gradlew check
```

The Initializr-generated `<App>ApplicationTests.kt` covers the boot smoke test.
Do not delete it.

## Versions

Pin via Spring Initializr at scaffold time. Reference: <https://start.spring.io/>.
Never write "Spring Boot 3.x.y" into any scaffolded file.
