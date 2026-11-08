---
name: angular-conventions
description: Modern Angular (v18+) coding standards — signals, standalone, OnPush, inject(), built-in control flow. Use when writing, refactoring or reviewing Angular code.
---

# Angular Conventions

Project rules (lint config, existing patterns) override these.

Components:
- Standalone (default since v19 — don't write `standalone: true`). Always `ChangeDetectionStrategy.OnPush`.
- Import only the pipes/directives used, never `CommonModule`.
- Host bindings in `host: {}` metadata, not `@HostBinding`/`@HostListener`.
- Template-only members `protected`; internals `#private`.

Signals:
- `input()`, `input.required()`, `output()`, `model()` — no `@Input`/`@Output`, no `Signal` suffix, no aliases.
- State `signal()`, derived `computed()`, writable derived `linkedSignal()`.
- Update with `set`/`update` returning new objects/arrays — never mutate.
- `effect()` only for real side effects (DOM libs, analytics), never to copy state between signals.

DI:
- `readonly #api: ApiService = inject(ApiService);` — empty or no constructor.
- Stateless services `providedIn: 'root'`; config through typed `InjectionToken<T>`.

Templates:
- `@if`, `@for`, `@switch` only. Every `@for` has `track item.id` (`$index` only for primitives); add `@empty` where a list can be empty.
- No method calls in bindings (`{{ total() }}` of a `computed` is fine, `{{ calcTotal() }}` is not) — use `computed()` or a pure pipe.
- `[class.x]`/`[style.x]` instead of `ngClass`/`ngStyle`.

Types and errors:
- No `any`. External data is `unknown`, narrowed by a type guard or schema (Zod/Valibot).
- No silent `catchError(() => of(null))` — log and expose an error state. No `console.log`.

```typescript
@Component({
  selector: 'app-user-card',
  templateUrl: './user-card.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { '[class.active]': 'active()', '(click)': 'select.emit(user().id)' },
})
export class UserCardComponent {
  readonly user = input.required<User>();
  readonly active = input(false);
  readonly select = output<string>();
  readonly #format: NameFormatter = inject(NameFormatter);
  protected readonly name = computed(() => this.#format.full(this.user()));
}
```

Tests: `*.spec.ts` next to the file; test inputs, outputs and user interaction, not private details.
