// Test-only constructor recorder, not a Schemastery implementation or validator.
// It deliberately has no native identity, ~standard validator, or projector.
class SchemaCall {
  constructor(type, dict) { this.type = type; this.dict = dict; this.meta = {}; }
  default(value) { this.meta.default = value; return this; }
  description(value) { this.meta.description = value; return this; }
  i18n(messages) { this.localeCalls = messages; return this; }
}
export default {
  boolean: () => new SchemaCall('boolean'),
  string: () => new SchemaCall('string'),
  object: dict => new SchemaCall('object', dict),
};
