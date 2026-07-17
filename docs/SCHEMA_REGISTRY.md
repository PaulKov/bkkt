# Schema Registry guide

```bash
bkkt schema subjects list --env dev --cluster local
bkkt schema subject describe SUBJECT --env dev --cluster local
bkkt schema compatibility check SUBJECT --schema-file schema.avsc --env dev --cluster local
```

## Registration safety

Register/update operations are gated:

```bash
bkkt schema register SUBJECT --schema-file schema.avsc --env dev --cluster local --dry-run
bkkt schema register SUBJECT --schema-file schema.avsc --env dev --cluster local --yes
```

Keep Avro/JSON/Protobuf schema files in Git next to connector manifests when
they define the contract for a topic.
