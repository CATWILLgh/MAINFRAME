# Python validation boundaries

Use the validator already established on the active path. Validate untrusted input at runtime; inside the validated boundary, rely on types and domain invariants instead of repeatedly parsing the same object.

## Pydantic

- Establish the installed major before using validators, settings, or serialization APIs.
- Use constrained fields and field or model validators for invariants that belong to the input contract.
- Separate request and response models when their accepted and exposed fields differ. Reuse is acceptable when the contracts genuinely match.
- Configure unknown-field behavior deliberately: rejecting protects strict contracts; ignoring can support compatibility where extra fields are expected.
- Omit sensitive or internal values from response schemas rather than hoping later serialization removes them.

## Marshmallow

- Use `load` for validation and deserialization and `dump` for serialization.
- Choose `unknown=RAISE`, `EXCLUDE`, or `INCLUDE` from the external contract rather than a global preference.
- Use schema-level validation for cross-field invariants and keep database-dependent business rules in the owning service.

## Django REST Framework

- Use `ModelSerializer` when direct model mapping is the intended API; use `Serializer` for commands, filters, or contracts that do not mirror one model.
- Mark writable and readable fields explicitly. Treat nested writes as a deliberate transactional contract, not a free consequence of nested output.
- Keep object authorization outside serializer shape validation.

## Sources

- Pydantic models — https://docs.pydantic.dev/latest/concepts/models/
- Marshmallow — https://marshmallow.readthedocs.io/
- DRF serializers — https://www.django-rest-framework.org/api-guide/serializers/
