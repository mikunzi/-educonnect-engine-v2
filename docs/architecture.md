# Clean Architecture

EduConnect Engine v2 is organized around bounded contexts:

- accounting
- finance
- tax
- reporting
- ai
- companies
- documents
- pedagogy
- workflows

Supporting platform modules:

- core
- shared

Each context follows the same layered structure:

1. `domain`
2. `application`
3. `infrastructure`
4. `presentation`

## Dependency Rule

Source code dependencies point inward.

- `presentation` may depend on `application`.
- `application` may depend on `domain`.
- `infrastructure` may depend on `application` and `domain` to implement ports.
- `domain` depends on nothing outside shared kernel abstractions.

## DDD Boundaries

- Each bounded context owns its own domain models and repository ports.
- Cross-context collaboration should happen through application services and explicit contracts.
- Shared primitives belong in `shared`; technical orchestration belongs in `core`.

## SOLID in This Skeleton

- Single Responsibility: each layer/package has one concern.
- Open/Closed: behavior extends through interfaces and adapters.
- Liskov Substitution: repository contracts use protocols.
- Interface Segregation: ports are fine-grained per bounded context.
- Dependency Inversion: use cases depend on repository protocols, not concrete implementations.

No business rules are implemented yet.
