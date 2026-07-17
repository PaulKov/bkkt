# Справочник CLI: `bkkt` / `connectctl`

Этот документ **генерируется автоматически** из актуального `argparse --help`.

- Команда генерации: `bkkt docs generate-cli-reference`
- Живые примеры: `docs/CLI_EXAMPLES.md`

⚠️ Не редактируйте блок **Команды** вручную — он перезаписывается генератором.

## Команды

<!-- BKKT_CLI_REFERENCE_COMMANDS_START -->
### `bkkt --help` (общая справка)

```text
использование: bkkt [-h] [--repo-root REPO_ROOT] [--version] [--config CONFIG] [--explain-routing] [--explain-vars] [--explain-vars-keys EXPLAIN_VARS_KEYS] [--explain-vars-max EXPLAIN_VARS_MAX] {help,completion,config,functions,vars,repo,docs,demo,oss,inspect,search,find,lineage,render,compare,plan,diff,drift,get-connector,apply,export,reconcile,kafka,schema,connect,sync,init,validate,validate-connect} ...

BKKT — Best Kafka Connectors Tool (GitOps CI/CD для Kafka Connect коннекторов)

позиционные аргументы:
  {help,completion,config,functions,vars,repo,docs,demo,oss,inspect,search,find,lineage,render,compare,plan,diff,drift,get-connector,apply,export,reconcile,kafka,schema,connect,sync,init,validate,validate-connect}
    help                Короткие примеры команд (шпаргалка из
                        docs/CLI_EXAMPLES.md)
    completion          Сгенерировать shell snippet для автодополнения
                        (argcomplete)
    config              Manage connectctl.yaml
    functions           Repo-local `${fn:...}` function registry and
                        diagnostics
    vars                Inspect BKKT placeholder variables and provenance
    repo                Repository operations
    docs                Documentation utilities
    demo                Local OSS-friendly demo scaffold
    oss                 OSS readiness, public-asset hygiene and v1.0 checks
    inspect             Показать метаданные и routing для конкретного
                        манифеста
    search              Гибкий поиск коннекторов по repo/live фактам и config-
                        предикатам
    find                (алиас) search
    lineage             Build a source/topic/sink/table lineage graph for an
                        object
    render              Отрендерить финальный manifest (после layered
                        overrides)
    compare             Сравнить один rendered manifest с live-коннектором или
                        внешним config-файлом
    plan                Посчитать, что apply/delete по git diff
    diff                Сравнение desired (render) конфига с live Kafka
                        Connect
    drift               Собрать отчёт о дрейфе (repo manifests vs live Kafka
                        Connect) для окружения
    get-connector       Показать config (и опционально status) конкретного
                        коннектора
    apply               Применить (deploy/update) коннекторы в Kafka Connect
                        через REST API
    export              Экспортировать существующие конфиги коннекторов из
                        Kafka Connect в репозиторий (bootstrap GitOps)
    reconcile           Prepare live-to-Git reconciliation using BKKT export
                        planning
    kafka               Kafka platform operations
    schema              Schema Registry governance
    connect             Kafka Connect REST client
    sync                Синхронизировать окружение: применить все манифесты из
                        репозитория и (опционально) prune лишние
    init                Сгенерировать структуру коннектора и манифест(ы)
    validate            Валидация манифестов (render + базовые проверки)
    validate-connect    Валидировать отрендеренные конфиги через Kafka Connect
                        plugin validate endpoint (без deploy)

опции:
  -h, --help            показать эту справку и выйти
  --repo-root REPO_ROOT
                        Корень репозитория (по умолчанию: .)
  --version             Print BKKT version and exit
  --config CONFIG       Путь к connectctl.yaml (по умолчанию ищется в
                        репозитории)
  --explain-routing     Пояснить выбор cluster group для коннектора: какой
                        слой/тег/дефолт победил
  --explain-vars        Пояснить происхождение config-ключей: из какого слоя
                        взято итоговое значение
  --explain-vars-keys EXPLAIN_VARS_KEYS
                        Фильтр ключей для --explain-vars. Можно указать
                        несколько паттернов через запятую (regex или
                        подстрока). Пример: 'snapshot|transforms,errors'
  --explain-vars-max EXPLAIN_VARS_MAX
                        Максимум ключей для вывода в --explain-vars (0 = без
                        лимита). По умолчанию: 200
```

### `bkkt help --help`

```text
использование: bkkt help [-h] [--list] [topic ...]

позиционные аргументы:
  topic       Тема/команда. Например: `help diff` или `help connect status`
              (по умолчанию: показать список тем)

опции:
  -h, --help  показать эту справку и выйти
  --list      Показать список доступных тем и выйти
```

### `bkkt completion --help`

```text
использование: bkkt completion [-h] --shell {bash,zsh,fish} [--program PROGRAM] [--no-comments] [--install] [--dry-run] [--system] [--rc-file RC_FILE] [-y]

опции:
  -h, --help            показать эту справку и выйти
  --shell {bash,zsh,fish}
                        Целевая оболочка
  --program PROGRAM     Имя CLI entrypoint (bkkt или connectctl). По
                        умолчанию: bkkt
  --no-comments         Вывести только snippet без комментариев (удобно для
                        eval "$(...)")
  --install             Автоматически установить автодополнение в конфиг
                        оболочки (с подтверждением)
  --dry-run             Предпросмотр установки: показать, куда будет
                        установлен completion и какой diff будет применён, но
                        ничего не изменять на диске. Если указано без
                        --install — BKKT автоматически переходит в режим
                        предпросмотра.
  --system              Установить completion в системный путь (для всех
                        пользователей). Может потребоваться sudo. BKKT
                        автоматически подбирает системный путь в зависимости
                        от ОС (Linux/macOS) и наличия каталогов. Примеры
                        путей: bash=/etc/bash_completion.d/<program> или
                        /opt/homebrew/etc/bash_completion.d/<program>,
                        zsh=/etc/zshrc, fish=/usr/share/fish/vendor_completion
                        s.d/<program>.fish.
  --rc-file RC_FILE     Путь для установки completion. По умолчанию: ~/.bashrc
                        (bash), ~/.zshrc (zsh),
                        ~/.config/fish/completions/<program>.fish (fish).
  -y, --yes             Не спрашивать подтверждение при --install
```

### `bkkt config --help`

```text
использование: bkkt config [-h] {validate,clusters,runtimes,find,hosts,explain,render} ...

позиционные аргументы:
  {validate,clusters,runtimes,find,hosts,explain,render}
    validate            Проверить connectctl.yaml
                        (кластера/наследование/валидность)
    clusters            Показать cluster groups/env/Connect URLs/Kafka hosts
                        из connectctl.yaml
    runtimes            Kafka Connect runtime inventory and validation
    find                Найти cluster/env по Connect host, Kafka bootstrap или
                        Schema Registry
    hosts               Проверить/добавить/удалить Kafka Connect REST hosts в
                        connectctl.yaml
    explain             Показать итоговый resolved config для cluster
                        group/env
    render              Вывести финальный connectctl.yaml (после
                        from_cluster_group_env и env var подстановок)

опции:
  -h, --help            показать эту справку и выйти
```

#### `bkkt config validate --help`

```text
использование: bkkt config validate [-h] [--strict] [--output {text,json,yaml}] [--json]

опции:
  -h, --help            показать эту справку и выйти
  --strict              Считать предупреждения ошибками (ненулевой exit code)
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
```

#### `bkkt config clusters --help`

```text
использование: bkkt config clusters [-h] [--cluster-group CLUSTER_GROUP] [--env ENV] [--show-render-vars] [--hide-kafka-bootstrap] [--hide-schema-registry] [--no-provenance] [--view {short,long,details}] [--output {text,json,yaml}] [--json]

опции:
  -h, --help            показать эту справку и выйти
  --cluster-group, --cluster CLUSTER_GROUP
                        Фильтр по cluster group (можно несколько раз или через
                        запятую). Alias: --cluster.
  --env ENV             Фильтр по окружению (dev|stage|prod). Можно несколько
                        раз или через запятую.
  --show-render-vars    Показать render.vars и render.prune_config_keys для
                        выбранных scopes (секреты маскируются эвристикой по
                        имени ключа).
  --hide-kafka-bootstrap
                        Не показывать колонку Kafka bootstrap в text-выводе
  --hide-schema-registry
                        Не показывать колонку Schema Registry в text-выводе
  --no-provenance       Не печатать Notes/provenance блок в text-выводе
  --view {short,long,details}
                        Text view mode: short|long|details. По умолчанию: long
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
```

#### `bkkt config runtimes --help`

```text
использование: bkkt config runtimes [-h] {list,explain,check} ...

позиционные аргументы:
  {list,explain,check}
    list                List configured Connect runtimes
    explain             Explain one Connect runtime scope
    check               Run static checks for configured Connect runtimes

опции:
  -h, --help            показать эту справку и выйти
```

##### `bkkt config runtimes list --help`

```text
использование: bkkt config runtimes list [-h] [--cluster-group CLUSTER_GROUP] [--env ENV] [--output {text,json,yaml}] [--json]

опции:
  -h, --help            показать эту справку и выйти
  --cluster-group, --cluster CLUSTER_GROUP
                        Фильтр по cluster group (можно несколько раз или через
                        запятую). Alias: --cluster.
  --env ENV             Фильтр по окружению (dev|stage|prod). Можно несколько
                        раз или через запятую.
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
```

##### `bkkt config runtimes explain --help`

```text
использование: bkkt config runtimes explain [-h] [--cluster-group CLUSTER_GROUP] [--env ENV] [--output {text,json,yaml}] [--json]

опции:
  -h, --help            показать эту справку и выйти
  --cluster-group, --cluster CLUSTER_GROUP
                        Фильтр по cluster group (можно несколько раз или через
                        запятую). Alias: --cluster.
  --env ENV             Фильтр по окружению (dev|stage|prod). Можно несколько
                        раз или через запятую.
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
```

##### `bkkt config runtimes check --help`

```text
использование: bkkt config runtimes check [-h] [--cluster-group CLUSTER_GROUP] [--env ENV] [--output {text,json,yaml}] [--json]

опции:
  -h, --help            показать эту справку и выйти
  --cluster-group, --cluster CLUSTER_GROUP
                        Фильтр по cluster group (можно несколько раз или через
                        запятую). Alias: --cluster.
  --env ENV             Фильтр по окружению (dev|stage|prod). Можно несколько
                        раз или через запятую.
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
```

#### `bkkt config find --help`

```text
использование: bkkt config find [-h] [--cluster-group CLUSTER_GROUP] [--env ENV] [--connect-host CONNECT_HOST] [--kafka-bootstrap KAFKA_BOOTSTRAP] [--schema-registry-url SCHEMA_REGISTRY_URL] [--connector CONNECTOR] [--output {text,json,yaml}] [--json]

опции:
  -h, --help            показать эту справку и выйти
  --cluster-group, --cluster CLUSTER_GROUP
                        Фильтр по cluster group (можно несколько раз или через
                        запятую). Alias: --cluster.
  --env ENV             Фильтр по окружению (dev|stage|prod). Можно несколько
                        раз или через запятую.
  --connect-host CONNECT_HOST
                        Искать по Kafka Connect REST host/IP/host:port
  --kafka-bootstrap KAFKA_BOOTSTRAP
                        Искать по Kafka bootstrap host/IP/host:port
  --schema-registry-url, --schema-registry SCHEMA_REGISTRY_URL
                        Искать по Schema Registry URL/host/IP/host:port
  --connector CONNECTOR
                        Connector name hint; connector-level lookup is
                        delegated to bkkt search
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
```

#### `bkkt config hosts --help`

```text
использование: bkkt config hosts [-h] {check,add,remove} ...

позиционные аргументы:
  {check,add,remove}
    check             Проверить health Connect REST hosts
    add               Добавить Connect REST host(s) в scope
    remove            Удалить Connect REST host(s) из scope

опции:
  -h, --help          показать эту справку и выйти
```

##### `bkkt config hosts check --help`

```text
использование: bkkt config hosts check [-h] [--cluster-group CLUSTER_GROUP] [--env ENV] [--connect-host CONNECT_HOST] [--timeout-seconds TIMEOUT_SECONDS] [--jobs JOBS] [--rate-limit-per-second RATE_LIMIT_PER_SECOND] [--output {text,json,yaml}] [--json]

опции:
  -h, --help            показать эту справку и выйти
  --cluster-group, --cluster CLUSTER_GROUP
                        Фильтр по cluster group (можно несколько раз или через
                        запятую). Alias: --cluster.
  --env ENV             Фильтр по окружению (dev|stage|prod). Можно несколько
                        раз или через запятую.
  --connect-host, --host CONNECT_HOST
                        Kafka Connect REST host/IP без scheme; можно повторять
                        или передавать CSV
  --timeout-seconds TIMEOUT_SECONDS
                        HTTP timeout на один endpoint, по умолчанию 5 секунд
  --jobs JOBS           Параллелизм (кол-во потоков) для массовых операций. По
                        умолчанию: 8
  --rate-limit-per-second RATE_LIMIT_PER_SECOND
                        Ограничение REST запросов в секунду (RPS) ко всем
                        Connect URL вместе. Если не задано и --jobs > 1,
                        включается безопасный лимит (по умолчанию ~5 RPS). 0 =
                        выключить ограничение.
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
```

##### `bkkt config hosts add --help`

```text
использование: bkkt config hosts add [-h] --cluster-group CLUSTER_GROUP --env ENV [--connect-host CONNECT_HOST] [--skip-health-check] [--dry-run] [--yes] [--output {text,json,yaml}] [--json]

опции:
  -h, --help            показать эту справку и выйти
  --cluster-group, --cluster CLUSTER_GROUP
                        Фильтр по cluster group (можно несколько раз или через
                        запятую). Alias: --cluster.
  --env ENV             Фильтр по окружению (dev|stage|prod). Можно несколько
                        раз или через запятую.
  --connect-host, --host CONNECT_HOST
                        Kafka Connect REST host/IP без scheme; можно повторять
                        или передавать CSV
  --skip-health-check   Не делать preflight health check перед записью host(s)
  --dry-run             Ничего не записывать, только показать план и diff
  --yes, -y             Подтвердить запись изменений в repo config
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
```

##### `bkkt config hosts remove --help`

```text
использование: bkkt config hosts remove [-h] --cluster-group CLUSTER_GROUP --env ENV [--connect-host CONNECT_HOST] [--dry-run] [--yes] [--output {text,json,yaml}] [--json]

опции:
  -h, --help            показать эту справку и выйти
  --cluster-group, --cluster CLUSTER_GROUP
                        Фильтр по cluster group (можно несколько раз или через
                        запятую). Alias: --cluster.
  --env ENV             Фильтр по окружению (dev|stage|prod). Можно несколько
                        раз или через запятую.
  --connect-host, --host CONNECT_HOST
                        Kafka Connect REST host/IP без scheme; можно повторять
                        или передавать CSV
  --dry-run             Ничего не записывать, только показать план и diff
  --yes, -y             Подтвердить запись изменений в repo config
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
```

#### `bkkt config explain --help`

```text
использование: bkkt config explain [-h] [--cluster-group CLUSTER_GROUP] --env ENV [--output {text,json,yaml}] [--json]

опции:
  -h, --help            показать эту справку и выйти
  --cluster-group CLUSTER_GROUP
                        Имя cluster group (по умолчанию: default_cluster из
                        connectctl.yaml)
  --env ENV             Окружение: dev|stage|prod
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
```

#### `bkkt config render --help`

```text
использование: bkkt config render [-h] [--cluster-group CLUSTER_GROUP] [--env ENV] [--show-secrets] [--output {text,json,yaml}] [--json] [--output-file OUTPUT_FILE] [-y]

опции:
  -h, --help            показать эту справку и выйти
  --cluster-group CLUSTER_GROUP
                        Фильтр по cluster group (можно несколько раз или через
                        запятую). По умолчанию: все группы из connectctl.yaml
  --env ENV             Фильтр по окружению (dev|stage|prod). Можно несколько
                        раз или через запятую. По умолчанию: все env в каждой
                        группе
  --show-secrets        Показывать секреты (не маскировать значения по ключам
                        password/token/secret/...).
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: yaml
  --json                Alias для --output json (устаревает, используйте
                        --output json)
  --output-file OUTPUT_FILE
                        (опционально) Записать результат в файл в том же
                        формате, что и stdout
  -y, --yes             Не спрашивать подтверждение для широкого текстового
                        render
```

### `bkkt functions --help`

```text
использование: bkkt functions [-h] {list,explain,run,doctor,coverage,test,validate-calls,contract,used-by,impact,review,lint,rename,deprecate,package,catalog,docs,scaffold} ...

позиционные аргументы:
  {list,explain,run,doctor,coverage,test,validate-calls,contract,used-by,impact,review,lint,rename,deprecate,package,catalog,docs,scaffold}
    list                List builtin and repo-local functions
    explain             Explain one registered function
    run                 Run a function locally for debugging
    doctor              Validate repo-local function loading
    coverage            Report repo-wide function usage and contract-test
                        coverage
    test                Run repo-local function contract tests
    validate-calls      Validate `${fn:...}` calls in one manifest
    contract            Generate and manage function contract tests
    used-by             Find manifests using a function
    impact              Find manifests affected by a function change
    review              Review function contracts, impact, and lock status
                        before a change
    lint                Lint repo-local function usage
    rename              Plan a safe repo-wide function rename without
                        rewriting manifests
    deprecate           Plan function deprecation metadata and usage impact
    package             Function namespace package UX
    catalog             Generate function catalog docs
    docs                Generate function reference docs
    scaffold            Create a repo-local function template

опции:
  -h, --help            показать эту справку и выйти
```

#### `bkkt functions list --help`

```text
использование: bkkt functions list [-h] [--output {text,json,yaml}] [--json]

опции:
  -h, --help            показать эту справку и выйти
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
```

#### `bkkt functions explain --help`

```text
использование: bkkt functions explain [-h] [--output {text,json,yaml}] [--json] name

позиционные аргументы:
  name                  Function name

опции:
  -h, --help            показать эту справку и выйти
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
```

#### `bkkt functions run --help`

```text
использование: bkkt functions run [-h] [--arg ARG] [--kw KW] [--manifest MANIFEST] [--contract-check] [--output {text,json,yaml}] [--json] name

позиционные аргументы:
  name                  Function name

опции:
  -h, --help            показать эту справку и выйти
  --arg ARG             Positional argument
  --kw KW               Keyword argument as key=value; value may be JSON
                        literal
  --manifest MANIFEST   Optional manifest path used to build the same variable
                        context as render
  --contract-check      Validate typed function arguments before executing the
                        function
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
```

#### `bkkt functions doctor --help`

```text
использование: bkkt functions doctor [-h] [--strict] [--output {text,json,yaml}] [--json]

опции:
  -h, --help            показать эту справку и выйти
  --strict              Also scan repo-local functions for risky non-
                        deterministic code
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
```

#### `bkkt functions coverage --help`

```text
использование: bkkt functions coverage [-h] [--strict] [--today TODAY] [--output {text,json,yaml}] [--json]

опции:
  -h, --help            показать эту справку и выйти
  --strict              Exit non-zero when governance coverage issues are
                        errors
  --today TODAY         ISO date used for remove_after checks (по умолчанию: today)
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
```

#### `bkkt functions test --help`

```text
использование: bkkt functions test [-h] [--pattern PATTERN] [--output {text,json,yaml}] [--json]

опции:
  -h, --help            показать эту справку и выйти
  --pattern PATTERN     Glob for YAML test files (по умолчанию:
                        bkkt/functions/tests/**/*.yaml)
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
```

#### `bkkt functions validate-calls --help`

```text
использование: bkkt functions validate-calls [-h] [--output {text,json,yaml}] [--json] manifest

позиционные аргументы:
  manifest              Manifest path

опции:
  -h, --help            показать эту справку и выйти
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
```

#### `bkkt functions contract --help`

```text
использование: bkkt functions contract [-h] {infer} ...

позиционные аргументы:
  {infer}
    infer     Create a function contract-test case from sample inputs

опции:
  -h, --help  показать эту справку и выйти
```

##### `bkkt functions contract infer --help`

```text
использование: bkkt functions contract infer [-h] [--arg ARG] [--kw KW] --expect EXPECT [--manifest MANIFEST] [--output-file OUTPUT_FILE] [--dry-run] [--overwrite] [--output {text,json,yaml}] [--json] name

позиционные аргументы:
  name                  Function name

опции:
  -h, --help            показать эту справку и выйти
  --arg ARG             Positional argument
  --kw KW               Keyword argument as key=value; value may be JSON
                        literal
  --expect EXPECT       Expected result; value may be JSON literal
  --manifest MANIFEST   Optional manifest context to include in the contract
                        case
  --output-file OUTPUT_FILE
                        Target YAML file (по умолчанию:
                        bkkt/functions/tests/<name>.yaml)
  --dry-run             Print contract only
  --overwrite           Allow replacing an existing --output-file
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
```

#### `bkkt functions used-by --help`

```text
использование: bkkt functions used-by [-h] [--output {text,json,yaml}] [--json] name

позиционные аргументы:
  name                  Function name

опции:
  -h, --help            показать эту справку и выйти
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
```

#### `bkkt functions impact --help`

```text
использование: bkkt functions impact [-h] [--with-render-diff] [--output {text,json,yaml}] [--json] name

позиционные аргументы:
  name                  Function name

опции:
  -h, --help            показать эту справку и выйти
  --with-render-diff    Render affected manifests and report config diffs if
                        any
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
```

#### `bkkt functions review --help`

```text
использование: bkkt functions review [-h] [--with-render-diff] [--pattern PATTERN] [--lock-file LOCK_FILE] [--output {text,json,yaml}] [--json] name

позиционные аргументы:
  name                  Function name

опции:
  -h, --help            показать эту справку и выйти
  --with-render-diff    Render affected manifests and include config diffs if
                        any
  --pattern PATTERN     Glob for YAML function contract files
  --lock-file LOCK_FILE
                        Function lockfile path. По умолчанию:
                        bkkt/functions.lock.yaml
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
```

#### `bkkt functions lint --help`

```text
использование: bkkt functions lint [-h] [--unused] [--output {text,json,yaml}] [--json]

опции:
  -h, --help            показать эту справку и выйти
  --unused              Report repo-local functions that are declared but
                        never used
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
```

#### `bkkt functions rename --help`

```text
использование: bkkt functions rename [-h] [--dry-run] [--output {text,json,yaml}] [--json] old_name new_name

позиционные аргументы:
  old_name              Current function name
  new_name              New function name

опции:
  -h, --help            показать эту справку и выйти
  --dry-run             Required in v1; prints the reviewable rename plan
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
```

#### `bkkt functions deprecate --help`

```text
использование: bkkt functions deprecate [-h] [--replacement REPLACEMENT] [--remove-after REMOVE_AFTER] [--dry-run] [--output {text,json,yaml}] [--json] name

позиционные аргументы:
  name                  Function name

опции:
  -h, --help            показать эту справку и выйти
  --replacement REPLACEMENT
                        Replacement function name
  --remove-after REMOVE_AFTER
                        Target removal date
  --dry-run             Required in v1; prints the reviewable deprecation plan
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
```

#### `bkkt functions package --help`

```text
использование: bkkt functions package [-h] {list,doctor,lock,diff,check,docs} ...

позиционные аргументы:
  {list,doctor,lock,diff,check,docs}
    list                List function packages
    doctor              Validate function package hygiene
    lock                Create or check the repo-local function lockfile
    diff                Diff lockfile vs current functions
    check               Run function lock and impact gate checks
    docs                Generate function package docs

опции:
  -h, --help            показать эту справку и выйти
```

##### `bkkt functions package list --help`

```text
использование: bkkt functions package list [-h] [--output {text,json,yaml}] [--json]

опции:
  -h, --help            показать эту справку и выйти
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
```

##### `bkkt functions package doctor --help`

```text
использование: bkkt functions package doctor [-h] [--strict] [--output {text,json,yaml}] [--json]

опции:
  -h, --help            показать эту справку и выйти
  --strict              Include strict deterministic capability diagnostics
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
```

##### `bkkt functions package lock --help`

```text
использование: bkkt functions package lock [-h] [--write] [--check] [--lock-file LOCK_FILE] [--output {text,json,yaml}] [--json]

опции:
  -h, --help            показать эту справку и выйти
  --write               Write the current lockfile instead of printing it
  --check               Check the existing lockfile against current functions
  --lock-file LOCK_FILE
                        Lockfile path. По умолчанию: bkkt/functions.lock.yaml
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
```

##### `bkkt functions package diff --help`

```text
использование: bkkt functions package diff [-h] [--lock-file LOCK_FILE] [--output {text,json,yaml}] [--json]

опции:
  -h, --help            показать эту справку и выйти
  --lock-file LOCK_FILE
                        Lockfile path. По умолчанию: bkkt/functions.lock.yaml
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
```

##### `bkkt functions package check --help`

```text
использование: bkkt functions package check [-h] [--lock-file LOCK_FILE] [--impact-artifact IMPACT_ARTIFACT] [--output {text,json,yaml}] [--json]

опции:
  -h, --help            показать эту справку и выйти
  --lock-file LOCK_FILE
                        Lockfile path. По умолчанию: bkkt/functions.lock.yaml
  --impact-artifact IMPACT_ARTIFACT
                        Optional YAML/JSON artifact acknowledging changed
                        functions
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
```

##### `bkkt functions package docs --help`

```text
использование: bkkt functions package docs [-h] {generate} ...

позиционные аргументы:
  {generate}
    generate  Generate docs for one package

опции:
  -h, --help  показать эту справку и выйти
```

###### `bkkt functions package docs generate --help`

```text
использование: bkkt functions package docs generate [-h] --output-file OUTPUT_FILE name

позиционные аргументы:
  name                  Package name, for example `platform`

опции:
  -h, --help            показать эту справку и выйти
  --output-file OUTPUT_FILE
                        Target Markdown file
```

#### `bkkt functions catalog --help`

```text
использование: bkkt functions catalog [-h] {generate} ...

позиционные аргументы:
  {generate}
    generate  Generate Markdown catalog from function coverage

опции:
  -h, --help  показать эту справку и выйти
```

##### `bkkt functions catalog generate --help`

```text
использование: bkkt functions catalog generate [-h] --output-file OUTPUT_FILE [--output {text,json,yaml}] [--json]

опции:
  -h, --help            показать эту справку и выйти
  --output-file OUTPUT_FILE
                        Target Markdown file
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
```

#### `bkkt functions docs --help`

```text
использование: bkkt functions docs [-h] {generate} ...

позиционные аргументы:
  {generate}
    generate  Generate Markdown docs for registered functions

опции:
  -h, --help  показать эту справку и выйти
```

##### `bkkt functions docs generate --help`

```text
использование: bkkt functions docs generate [-h] --output-file OUTPUT_FILE

опции:
  -h, --help            показать эту справку и выйти
  --output-file OUTPUT_FILE
                        Target Markdown file
```

#### `bkkt functions scaffold --help`

```text
использование: bkkt functions scaffold [-h] [--path PATH] [--with-fixture] [--contract-path CONTRACT_PATH] [--fixture-path FIXTURE_PATH] [--template-test-path TEMPLATE_TEST_PATH] [--overwrite] [--dry-run] [--output {text,json,yaml}] [--json] name

позиционные аргументы:
  name                  Function name

опции:
  -h, --help            показать эту справку и выйти
  --path PATH           Target Python file relative to repo root
  --with-fixture        Also create a function contract and golden render
                        fixture/test
  --contract-path CONTRACT_PATH
                        Optional function contract test path relative to repo
                        root
  --fixture-path FIXTURE_PATH
                        Optional render fixture manifest path relative to repo
                        root
  --template-test-path TEMPLATE_TEST_PATH
                        Optional golden template test path relative to repo
                        root
  --overwrite           Allow replacing existing generated scaffold files
  --dry-run             Print template only
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
```

### `bkkt vars --help`

```text
использование: bkkt vars [-h] {list,explain,resolve,trace,doctor,coverage,validate-repo,graph,used-by,impact,review,lint,rename,deprecate,preflight,profile,schema,catalog,docs,providers,computed} ...

позиционные аргументы:
  {list,explain,resolve,trace,doctor,coverage,validate-repo,graph,used-by,impact,review,lint,rename,deprecate,preflight,profile,schema,catalog,docs,providers,computed}
    list                List effective variables for a manifest
    explain             Explain variables for a manifest
    resolve             Resolve a placeholder expression
    trace               Explain one variable value and usages
    doctor              Validate typed vars schema for a manifest
    coverage            Report repo-wide variable usage and typed schema
                        coverage
    validate-repo       Validate every deployable manifest against vars schema
    graph               Show placeholder variable/function graph
    used-by             Find manifests using a variable
    impact              Find manifests affected by a variable change
    review              Review variable schema, usage impact, and optional
                        render diff
    lint                Lint repo variable declarations
    rename              Plan a safe repo-wide variable rename without
                        rewriting manifests
    deprecate           Plan variable deprecation metadata and usage impact
    preflight           Validate provider contracts and external variable
                        references
    profile             Named runtime vars profiles for safe dry-runs
    schema              Infer and manage typed vars schema
    catalog             Generate variable catalog docs
    docs                Generate variable reference docs
    providers           Repo-local variable providers and diagnostics
    computed            Repo-local computed variables and diagnostics

опции:
  -h, --help            показать эту справку и выйти
```

#### `bkkt vars list --help`

```text
использование: bkkt vars list [-h] [--output {text,json,yaml}] [--json] manifest

позиционные аргументы:
  manifest              Manifest path

опции:
  -h, --help            показать эту справку и выйти
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
```

#### `bkkt vars explain --help`

```text
использование: bkkt vars explain [-h] [--output {text,json,yaml}] [--json] manifest [key]

позиционные аргументы:
  manifest              Manifest path
  key                   Optional variable key

опции:
  -h, --help            показать эту справку и выйти
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
```

#### `bkkt vars resolve --help`

```text
использование: bkkt vars resolve [-h] --expr EXPR [--output {text,json,yaml}] [--json] manifest

позиционные аргументы:
  manifest              Manifest path

опции:
  -h, --help            показать эту справку и выйти
  --expr EXPR           Expression or string with placeholders
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
```

#### `bkkt vars trace --help`

```text
использование: bkkt vars trace [-h] [--include-contracts] [--output {text,json,yaml}] [--json] manifest key

позиционные аргументы:
  manifest              Manifest path
  key                   Variable key, for example `db.secret`

опции:
  -h, --help            показать эту справку и выйти
  --include-contracts   Include typed variable contract metadata in trace
                        output
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
```

#### `bkkt vars doctor --help`

```text
использование: bkkt vars doctor [-h] [--schema SCHEMA] [--output {text,json,yaml}] [--json] manifest

позиционные аргументы:
  manifest              Manifest path

опции:
  -h, --help            показать эту справку и выйти
  --schema SCHEMA       Vars schema path relative to repo root (по умолчанию:
                        bkkt/vars.schema.yaml)
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
```

#### `bkkt vars coverage --help`

```text
использование: bkkt vars coverage [-h] [--schema SCHEMA] [--strict] [--today TODAY] [--output {text,json,yaml}] [--json]

опции:
  -h, --help            показать эту справку и выйти
  --schema SCHEMA       Vars schema path relative to repo root (по умолчанию:
                        bkkt/vars.schema.yaml)
  --strict              Exit non-zero when governance coverage issues are
                        errors
  --today TODAY         ISO date used for remove_after checks (по умолчанию: today)
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
```

#### `bkkt vars validate-repo --help`

```text
использование: bkkt vars validate-repo [-h] [--schema SCHEMA] [--output {text,json,yaml}] [--json]

опции:
  -h, --help            показать эту справку и выйти
  --schema SCHEMA       Vars schema path relative to repo root (по умолчанию:
                        bkkt/vars.schema.yaml)
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
```

#### `bkkt vars graph --help`

```text
использование: bkkt vars graph [-h] [--format {payload,mermaid}] [--output {text,json,yaml}] [--json] manifest

позиционные аргументы:
  manifest              Manifest path

опции:
  -h, --help            показать эту справку и выйти
  --format {payload,mermaid}
                        Graph renderer for text output (по умолчанию: payload)
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
```

#### `bkkt vars used-by --help`

```text
использование: bkkt vars used-by [-h] [--output {text,json,yaml}] [--json] name

позиционные аргументы:
  name                  Variable key, for example `db.secret`

опции:
  -h, --help            показать эту справку и выйти
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
```

#### `bkkt vars impact --help`

```text
использование: bkkt vars impact [-h] [--with-render-diff] [--set KEY=VALUE] [--output {text,json,yaml}] [--json] name

позиционные аргументы:
  name                  Variable key, for example `db.secret`

опции:
  -h, --help            показать эту справку и выйти
  --with-render-diff    Render affected manifests before/after temporary
                        overrides
  --set KEY=VALUE       Temporary variable override used only for --with-
                        render-diff
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
```

#### `bkkt vars review --help`

```text
использование: bkkt vars review [-h] [--with-render-diff] [--set KEY=VALUE] [--schema SCHEMA] [--output {text,json,yaml}] [--json] name

позиционные аргументы:
  name                  Variable key, for example `db.secret`

опции:
  -h, --help            показать эту справку и выйти
  --with-render-diff    Render affected manifests before/after temporary
                        overrides
  --set KEY=VALUE       Temporary variable override used only for --with-
                        render-diff
  --schema SCHEMA       Vars schema path relative to repo root (по умолчанию:
                        bkkt/vars.schema.yaml)
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
```

#### `bkkt vars lint --help`

```text
использование: bkkt vars lint [-h] [--unused] [--schema SCHEMA] [--output {text,json,yaml}] [--json]

опции:
  -h, --help            показать эту справку и выйти
  --unused              Report vars schema entries that are declared but never
                        used
  --schema SCHEMA       Vars schema path relative to repo root (по умолчанию:
                        bkkt/vars.schema.yaml)
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
```

#### `bkkt vars rename --help`

```text
использование: bkkt vars rename [-h] [--schema SCHEMA] [--dry-run] [--output {text,json,yaml}] [--json] old_key new_key

позиционные аргументы:
  old_key               Current variable key
  new_key               New variable key

опции:
  -h, --help            показать эту справку и выйти
  --schema SCHEMA       Vars schema path relative to repo root (по умолчанию:
                        bkkt/vars.schema.yaml)
  --dry-run             Required in v1; prints the reviewable rename plan
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
```

#### `bkkt vars deprecate --help`

```text
использование: bkkt vars deprecate [-h] [--replacement REPLACEMENT] [--remove-after REMOVE_AFTER] [--schema SCHEMA] [--dry-run] [--output {text,json,yaml}] [--json] key

позиционные аргументы:
  key                   Variable key

опции:
  -h, --help            показать эту справку и выйти
  --replacement REPLACEMENT
                        Replacement variable key
  --remove-after REMOVE_AFTER
                        Target removal date
  --schema SCHEMA       Vars schema path relative to repo root (по умолчанию:
                        bkkt/vars.schema.yaml)
  --dry-run             Required in v1; prints the reviewable deprecation plan
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
```

#### `bkkt vars preflight --help`

```text
использование: bkkt vars preflight [-h] [--provider-contract PROVIDER_CONTRACT] [--secret-index SECRET_INDEX] [--output {text,json,yaml}] [--json] manifest

позиционные аргументы:
  manifest              Manifest path

опции:
  -h, --help            показать эту справку и выйти
  --provider-contract PROVIDER_CONTRACT
                        Provider contract file or directory relative to repo
                        root (по умолчанию: bkkt/var_providers/contracts/**/*.yaml)
  --secret-index SECRET_INDEX
                        Optional static secret reference index. Without it,
                        secret refs are reported as unverified warnings.
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
```

#### `bkkt vars profile --help`

```text
использование: bkkt vars profile [-h] {list,explain,diff} ...

позиционные аргументы:
  {list,explain,diff}
    list               List runtime vars profiles
    explain            Explain one runtime vars profile
    diff               Show how a vars profile changes one manifest context

опции:
  -h, --help           показать эту справку и выйти
```

##### `bkkt vars profile list --help`

```text
использование: bkkt vars profile list [-h] [--output {text,json,yaml}] [--json]

опции:
  -h, --help            показать эту справку и выйти
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
```

##### `bkkt vars profile explain --help`

```text
использование: bkkt vars profile explain [-h] [--output {text,json,yaml}] [--json] name

позиционные аргументы:
  name                  Profile name

опции:
  -h, --help            показать эту справку и выйти
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
```

##### `bkkt vars profile diff --help`

```text
использование: bkkt vars profile diff [-h] [--output {text,json,yaml}] [--json] name manifest

позиционные аргументы:
  name                  Profile name
  manifest              Manifest path

опции:
  -h, --help            показать эту справку и выйти
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
```

#### `bkkt vars schema --help`

```text
использование: bkkt vars schema [-h] {infer} ...

позиционные аргументы:
  {infer}
    infer     Infer a starter vars schema from rendered repo manifests

опции:
  -h, --help  показать эту справку и выйти
```

##### `bkkt vars schema infer --help`

```text
использование: bkkt vars schema infer [-h] [--from-repo] [--output-file OUTPUT_FILE] [--dry-run] [--overwrite] [--output {text,json,yaml}] [--json]

опции:
  -h, --help            показать эту справку и выйти
  --from-repo           Infer from all deployable manifests in the current
                        repo
  --output-file OUTPUT_FILE
                        Target schema file relative to repo root when not
                        using --dry-run
  --dry-run             Print schema without writing
  --overwrite           Allow replacing an existing --output-file
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
```

#### `bkkt vars catalog --help`

```text
использование: bkkt vars catalog [-h] {generate} ...

позиционные аргументы:
  {generate}
    generate  Generate Markdown catalog from variable coverage

опции:
  -h, --help  показать эту справку и выйти
```

##### `bkkt vars catalog generate --help`

```text
использование: bkkt vars catalog generate [-h] --output-file OUTPUT_FILE [--schema SCHEMA] [--output {text,json,yaml}] [--json]

опции:
  -h, --help            показать эту справку и выйти
  --output-file OUTPUT_FILE
                        Target Markdown file
  --schema SCHEMA       Vars schema path relative to repo root (по умолчанию:
                        bkkt/vars.schema.yaml)
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
```

#### `bkkt vars docs --help`

```text
использование: bkkt vars docs [-h] {generate} ...

позиционные аргументы:
  {generate}
    generate  Generate Markdown docs for vars schema entries

опции:
  -h, --help  показать эту справку и выйти
```

##### `bkkt vars docs generate --help`

```text
использование: bkkt vars docs generate [-h] --output-file OUTPUT_FILE [--schema SCHEMA]

опции:
  -h, --help            показать эту справку и выйти
  --output-file OUTPUT_FILE
                        Target Markdown file
  --schema SCHEMA       Vars schema path relative to repo root (по умолчанию:
                        bkkt/vars.schema.yaml)
```

#### `bkkt vars providers --help`

```text
использование: bkkt vars providers [-h] {list,explain,run,doctor,test,contract} ...

позиционные аргументы:
  {list,explain,run,doctor,test,contract}
    list                List repo-local variable providers
    explain             Explain one variable provider
    run                 Evaluate one variable provider for a manifest context
    doctor              Validate variable provider loading
    test                Run variable provider contracts
    contract            Variable provider contract authoring and validation

опции:
  -h, --help            показать эту справку и выйти
```

##### `bkkt vars providers list --help`

```text
использование: bkkt vars providers list [-h] [--output {text,json,yaml}] [--json]

опции:
  -h, --help            показать эту справку и выйти
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
```

##### `bkkt vars providers explain --help`

```text
использование: bkkt vars providers explain [-h] [--output {text,json,yaml}] [--json] name

позиционные аргументы:
  name                  Variable provider name

опции:
  -h, --help            показать эту справку и выйти
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
```

##### `bkkt vars providers run --help`

```text
использование: bkkt vars providers run [-h] [--manifest MANIFEST] [--output {text,json,yaml}] [--json] name

позиционные аргументы:
  name                  Variable provider name

опции:
  -h, --help            показать эту справку и выйти
  --manifest MANIFEST   Optional manifest path used to build render context
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
```

##### `bkkt vars providers doctor --help`

```text
использование: bkkt vars providers doctor [-h] [--output {text,json,yaml}] [--json]

опции:
  -h, --help            показать эту справку и выйти
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
```

##### `bkkt vars providers test --help`

```text
использование: bkkt vars providers test [-h] [--manifest MANIFEST] [--contract CONTRACT] [--output {text,json,yaml}] [--json]

опции:
  -h, --help            показать эту справку и выйти
  --manifest MANIFEST   Optional manifest path used to build provider context
  --contract CONTRACT   Provider contract file or directory relative to repo
                        root (по умолчанию: bkkt/var_providers/contracts/**/*.yaml)
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
```

##### `bkkt vars providers contract --help`

```text
использование: bkkt vars providers contract [-h] {infer,validate} ...

позиционные аргументы:
  {infer,validate}
    infer           Infer a starter contract for one variable provider
    validate        Validate variable providers against contracts

опции:
  -h, --help        показать эту справку и выйти
```

###### `bkkt vars providers contract infer --help`

```text
использование: bkkt vars providers contract infer [-h] [--manifest MANIFEST] [--output-file OUTPUT_FILE] [--dry-run] [--overwrite] [--output {text,json,yaml}] [--json] name

позиционные аргументы:
  name                  Variable provider name

опции:
  -h, --help            показать эту справку и выйти
  --manifest MANIFEST   Optional manifest path used to build provider context
  --output-file OUTPUT_FILE
                        Target contract file relative to repo root (по умолчанию:
                        bkkt/var_providers/contracts/<provider>.yaml)
  --dry-run             Print contract only
  --overwrite           Allow replacing an existing --output-file
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
```

###### `bkkt vars providers contract validate --help`

```text
использование: bkkt vars providers contract validate [-h] [--manifest MANIFEST] [--contract CONTRACT] [--output {text,json,yaml}] [--json]

опции:
  -h, --help            показать эту справку и выйти
  --manifest MANIFEST   Optional manifest path used to build provider context
  --contract CONTRACT   Provider contract file or directory relative to repo
                        root (по умолчанию: bkkt/var_providers/contracts/**/*.yaml)
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
```

#### `bkkt vars computed --help`

```text
использование: bkkt vars computed [-h] {list,explain,run,scaffold,doctor,test,graph,impact} ...

позиционные аргументы:
  {list,explain,run,scaffold,doctor,test,graph,impact}
    list                List repo-local computed variables
    explain             Explain one computed variable
    run                 Evaluate one computed variable for a manifest context
    scaffold            Create a repo-local computed variable template and
                        test
    doctor              Validate computed variable loading
    test                Run repo-local computed var tests
    graph               Show computed variable dependency graph
    impact              Find computed variables and manifests affected by a
                        computed var change

опции:
  -h, --help            показать эту справку и выйти
```

##### `bkkt vars computed list --help`

```text
использование: bkkt vars computed list [-h] [--output {text,json,yaml}] [--json]

опции:
  -h, --help            показать эту справку и выйти
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
```

##### `bkkt vars computed explain --help`

```text
использование: bkkt vars computed explain [-h] [--output {text,json,yaml}] [--json] name

позиционные аргументы:
  name                  Computed variable name

опции:
  -h, --help            показать эту справку и выйти
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
```

##### `bkkt vars computed run --help`

```text
использование: bkkt vars computed run [-h] [--manifest MANIFEST] [--output {text,json,yaml}] [--json] name

позиционные аргументы:
  name                  Computed variable name

опции:
  -h, --help            показать эту справку и выйти
  --manifest MANIFEST   Optional manifest path used to build render context
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
```

##### `bkkt vars computed scaffold --help`

```text
использование: bkkt vars computed scaffold [-h] [--path PATH] [--test-path TEST_PATH] [--dry-run] [--output {text,json,yaml}] [--json] name

позиционные аргументы:
  name                  Computed variable name, for example platform.topic

опции:
  -h, --help            показать эту справку и выйти
  --path PATH           Target Python file relative to repo root
  --test-path TEST_PATH
                        Target YAML contract file relative to repo root
                        (по умолчанию: bkkt/computed_vars/tests/<name>.yaml)
  --dry-run             Print templates only
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
```

##### `bkkt vars computed doctor --help`

```text
использование: bkkt vars computed doctor [-h] [--output {text,json,yaml}] [--json]

опции:
  -h, --help            показать эту справку и выйти
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
```

##### `bkkt vars computed test --help`

```text
использование: bkkt vars computed test [-h] [--pattern PATTERN] [--output {text,json,yaml}] [--json]

опции:
  -h, --help            показать эту справку и выйти
  --pattern PATTERN     Glob for YAML test files (по умолчанию:
                        bkkt/computed_vars/tests/**/*.yaml)
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
```

##### `bkkt vars computed graph --help`

```text
использование: bkkt vars computed graph [-h] [--format {payload,mermaid}] [--output {text,json,yaml}] [--json]

опции:
  -h, --help            показать эту справку и выйти
  --format {payload,mermaid}
                        Graph renderer for text output (по умолчанию: payload)
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
```

##### `bkkt vars computed impact --help`

```text
использование: bkkt vars computed impact [-h] [--output {text,json,yaml}] [--json] name

позиционные аргументы:
  name                  Computed variable name

опции:
  -h, --help            показать эту справку и выйти
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
```

### `bkkt repo --help`

```text
использование: bkkt repo [-h] {bootstrap,doctor,migrate-connector-dir} ...

позиционные аргументы:
  {bootstrap,doctor,migrate-connector-dir}
    bootstrap           Generate starter files for a BKKT manifests repository
                        (connectctl.yaml, __global, __init_templates, schemas)
    doctor              Проверить структуру репозитория манифестов (наличие
                        __global, init templates, ignore_dirs и т.д.)
    migrate-connector-dir
                        Нормализовать connector_dir к шаблону
                        connector_<domain>__<dataset>{__<suffix>}

опции:
  -h, --help            показать эту справку и выйти
```

#### `bkkt repo bootstrap --help`

```text
использование: bkkt repo bootstrap [-h] [--preset {full,minimal}] [--only {connectctl,global,init-templates,schemas}] [--init-templates-root INIT_TEMPLATES_ROOT] [--force] [--update] [--dry-run]

опции:
  -h, --help            показать эту справку и выйти
  --preset {full,minimal}
                        Which starter set to create: full=copied assets from
                        BKKT, minimal=create only lightweight placeholders.
                        по умолчанию: full
  --only {connectctl,global,init-templates,schemas}
                        Create only selected sections. Can be specified
                        multiple times. По умолчанию: connectctl + global + init-
                        templates.
  --init-templates-root INIT_TEMPLATES_ROOT
                        Where to write init templates (по умолчанию:
                        BKKT_INIT_TEMPLATES_ROOT or __init_templates). Useful
                        when your repo stores templates in a custom path.
  --force               Overwrite existing files (by default existing files
                        are skipped).
  --update              Safely refresh starter assets: if a file exists and
                        differs, BKKT will NOT overwrite it and will create a
                        neighboring *.bkkt.dist file instead. Useful after
                        upgrading the bkkt package. Cannot be combined with
                        --force.
  --dry-run             Show the plan and write nothing.
```

#### `bkkt repo doctor --help`

```text
использование: bkkt repo doctor [-h] [--strict] [--output {text,json,yaml}] [--json]

опции:
  -h, --help            показать эту справку и выйти
  --strict              Считать warning как ошибку (exit code != 0). Полезно
                        для CI.
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
```

#### `bkkt repo migrate-connector-dir --help`

```text
использование: bkkt repo migrate-connector-dir [-h] [--scope {all,changed}] [--base BASE] [--head HEAD] [--limit LIMIT] [--apply] [--dry-run] [-y] [--on-conflict {error,skip,suffix}] [--update-references] [--update-references-scope UPDATE_REFERENCES_SCOPE] [--output {text,json,yaml}] [--json]

опции:
  -h, --help            показать эту справку и выйти
  --scope {all,changed}
                        Область миграции: all=весь репозиторий, changed=только
                        затронутые git diff (base/head).
  --base BASE           Base git sha (для scope=changed; по умолчанию auto)
  --head HEAD           Head git sha (для scope=changed; по умолчанию HEAD)
  --limit LIMIT         Сколько элементов плана печатать (top-N). Остальные
                        будут свернуты как '… и ещё X…'.
  --apply               Выполнить переименование (по умолчанию команда
                        работает как dry-run и только показывает план).
  --dry-run             Явно включить dry-run (ничего не менять, только
                        показать план).
  -y, --yes             Не спрашивать подтверждение при --apply.
  --on-conflict {error,skip,suffix}
                        Что делать, если целевой каталог уже существует:
                        error=ошибка (default), skip=пропустить,
                        suffix=добавить __migrated для уникальности.
  --update-references   Попытаться обновить текстовые ссылки на старые пути
                        (README/docs/ci).
  --update-references-scope UPDATE_REFERENCES_SCOPE
                        Где искать ссылки для обновления (через запятую):
                        docs,ci,vscode,all. по умолчанию: docs,ci
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
```

### `bkkt docs --help`

```text
использование: bkkt docs [-h] {generate-cli-reference,update-dev-metrics} ...

позиционные аргументы:
  {generate-cli-reference,update-dev-metrics}
    generate-cli-reference
                        Сгенерировать docs/CLI_REFERENCE*.md из
                        argparse/--help (и опционально проверить актуальность)
    update-dev-metrics  Update autogenerated engineering metrics docs
                        (LOC/SLOC, coupling/cohesion) and optionally verify
                        freshness

опции:
  -h, --help            показать эту справку и выйти
```

#### `bkkt docs generate-cli-reference --help`

```text
использование: bkkt docs generate-cli-reference [-h] [--check] [--show-diff] [--diff-lines DIFF_LINES] [--target {all,md}] [--docs-dir DOCS_DIR]

опции:
  -h, --help            показать эту справку и выйти
  --check               Только проверить, что docs актуальны (не
                        перезаписывать). Exit!=0 если отличаются.
  --show-diff           При --check вывести unified diff для несовпадающих
                        файлов.
  --diff-lines DIFF_LINES
                        Сколько строк diff показывать на файл (по умолчанию: 200, 0
                        = не выводить).
  --target {all,md}     Какие файлы генерировать/проверять: all (default) | md
  --docs-dir DOCS_DIR   Каталог docs в репозитории (по умолчанию: docs)
```

#### `bkkt docs update-dev-metrics --help`

```text
использование: bkkt docs update-dev-metrics [-h] [--check] [--target {all,md}] [--docs-dir DOCS_DIR] [--top TOP]

опции:
  -h, --help           показать эту справку и выйти
  --check              Only verify that generated docs are up to date (do not
                       rewrite files).
  --target {all,md}    Which docs to update/check: all (default) | md
  --docs-dir DOCS_DIR  Docs directory relative to the repo root (по умолчанию:
                       docs)
  --top TOP            How many largest modules to show in the size table
                       (по умолчанию: 15)
```

### `bkkt demo --help`

```text
использование: bkkt demo [-h] {init,smoke} ...

позиционные аргументы:
  {init,smoke}
    init        Copy the bundled local Kafka/Connect/Schema Registry demo
                scaffold
    smoke       Validate bundled demo assets without requiring Docker-in-
                Docker

опции:
  -h, --help    показать эту справку и выйти
```

#### `bkkt demo init --help`

```text
использование: bkkt demo init [-h] [--output-dir OUTPUT_DIR] [--force] [--dry-run] [--output {text,json,yaml}]

опции:
  -h, --help            показать эту справку и выйти
  --output-dir OUTPUT_DIR
                        Directory where demo files will be written. По умолчанию:
                        bkkt-demo.
  --force               Overwrite existing demo files. By default existing
                        files are skipped.
  --dry-run             Show which files would be written without touching the
                        filesystem.
  --output {text,json,yaml}
                        Output format. По умолчанию: text.
```

#### `bkkt demo smoke --help`

```text
использование: bkkt demo smoke [-h] [--output-dir OUTPUT_DIR] [--keep] [--output {text,json,yaml}]

опции:
  -h, --help            показать эту справку и выйти
  --output-dir OUTPUT_DIR
                        Optional directory for generated smoke files. По умолчанию:
                        temporary directory.
  --keep                Keep generated smoke files. Requires --output-dir.
  --output {text,json,yaml}
                        Output format. По умолчанию: text.
```

### `bkkt oss --help`

```text
использование: bkkt oss [-h] {hygiene,readiness} ...

позиционные аргументы:
  {hygiene,readiness}
    hygiene            Scan public assets or the full repository for
                       secrets/internal references
    readiness          Run v1.0 OSS readiness checklist checks

опции:
  -h, --help           показать эту справку и выйти
```

#### `bkkt oss hygiene --help`

```text
использование: bkkt oss hygiene [-h] [--root ROOT] [--scope {public,repository}] [--output {text,json,yaml}]

опции:
  -h, --help            показать эту справку и выйти
  --root ROOT           Repository root to scan. По умолчанию: current directory.
  --scope {public,repository}
                        public=docs/demo assets; repository=hard-deny
                        secret/internal scan.
  --output {text,json,yaml}
                        Output format. По умолчанию: text.
```

#### `bkkt oss readiness --help`

```text
использование: bkkt oss readiness [-h] [--root ROOT] [--output {text,json,yaml}]

опции:
  -h, --help            показать эту справку и выйти
  --root ROOT           Repository root to check. По умолчанию: current directory.
  --output {text,json,yaml}
                        Output format. По умолчанию: text.
```

### `bkkt inspect --help`

```text
использование: bkkt inspect [-h] [--cluster CLUSTER] [--suppress-tag-conflicts] [--show-layers] [--show-vars] [--no-show-vars] [--vars VARS] [--vars-file VARS_FILE] [--vars-profile VARS_PROFILE] path

позиционные аргументы:
  path                  Путь к <env>.*.json манифесту (относительно корня
                        репозитория)

опции:
  -h, --help            показать эту справку и выйти
  --cluster CLUSTER     Переопределить cluster group (для отладки routing). По
                        умолчанию: по routing/default_cluster
  --suppress-tag-conflicts
                        Если несколько тегов задают один и тот же параметр
                        разными значениями: вывести warning и взять значение
                        последнего тега. Параметры из
                        tags.hard_conflict_params всегда приводят к ошибке.
  --show-layers         Показать список слоёв (low -> high)
  --show-vars           Печатать provenance vars (по умолчанию: включено)
  --no-show-vars        Отключить вывод provenance vars
  --vars VARS           dbt-style vars JSON (object). Можно повторять;
                        мерджится, побеждает последнее.
  --vars-file VARS_FILE
                        Путь к JSON/YAML vars (object). Можно повторять;
                        мерджится. Перебивается --vars.
  --vars-profile VARS_PROFILE
                        Имя профиля из bkkt/vars/profiles/*.yaml. Можно
                        повторять.
```

### `bkkt search --help`

```text
использование: bkkt search [-h] [--source {repo,live,both}] [--env ENV] [--cluster CLUSTER] [--view {short,long}] [--explain {long,stats,none}] [--limit LIMIT] [--ignore-case] [--list-vars] [-y] [--output {text,json,yaml}] [--json] [--jobs JOBS] [--rate-limit-per-second RATE_LIMIT_PER_SECOND] [--name NAME] [--name-prefix NAME_PREFIX] [--name-suffix NAME_SUFFIX] [--name-regexp NAME_REGEXP] [--name-fuzzy NAME_FUZZY] [--table TABLE] [--table-prefix TABLE_PREFIX] [--table-suffix TABLE_SUFFIX] [--table-regexp TABLE_REGEXP] [--table-match {any,all}] [--topic TOPIC] [--topic-prefix TOPIC_PREFIX] [--topic-suffix TOPIC_SUFFIX] [--topic-regexp TOPIC_REGEXP] [--topic-match {any,all}] [--domain DOMAIN] [--dataset DATASET] [--type {source,sink}] [--system SYSTEM] [--layer LAYER] [--mode MODE] [--kind KIND] [--host HOST] [--kafka-bootstrap KAFKA_BOOTSTRAP] [--schema-registry-url SCHEMA_REGISTRY_URL] [--database DATABASE] [--schema SCHEMA] [--server SERVER] [--has-config-key HAS_CONFIG_KEY] [--config-eq CONFIG_EQ] [--config-prefix CONFIG_PREFIX] [--config-suffix CONFIG_SUFFIX] [--config-regexp CONFIG_REGEXP] [--where WHERE] [--vars VARS] [--vars-file VARS_FILE] [--vars-profile VARS_PROFILE]

опции:
  -h, --help            показать эту справку и выйти
  --source {repo,live,both}
                        Где искать коннекторы: repo=отрендеренные manifests,
                        live=Kafka Connect, both=оба источника
  --env ENV             Окружение для поиска: dev|stage|prod|all (по
                        умолчанию: all)
  --cluster CLUSTER     Cluster group filter: <name>|all (по умолчанию: all)
  --view {short,long}   Формат текстового представления: short|long
  --explain {long,stats,none}
                        Explainable search output: long=match paths and
                        related occurrences, stats=compact config statistics
                        by env/cluster, none=legacy match output only
  --limit LIMIT         Ограничить число результатов
  --ignore-case         Игнорировать регистр для exact/prefix/suffix/regex
                        matching
  --list-vars           Показать разрешенные ${...} variables для search
                        filters и выйти
  -y, --yes             Не спрашивать подтверждение для широкого live поиска
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
  --jobs JOBS           Параллелизм (кол-во потоков) для массовых операций. По
                        умолчанию: 8
  --rate-limit-per-second RATE_LIMIT_PER_SECOND
                        Ограничение REST запросов в секунду (RPS) ко всем
                        Connect URL вместе. Если не задано и --jobs > 1,
                        включается безопасный лимит (по умолчанию ~5 RPS). 0 =
                        выключить ограничение.
  --name NAME           Точное совпадение имени коннектора (можно повторять,
                        CSV тоже поддерживается)
  --name-prefix NAME_PREFIX
                        Искать коннекторы по prefix имени
  --name-suffix NAME_SUFFIX
                        Искать коннекторы по suffix имени
  --name-regexp NAME_REGEXP
                        Искать коннекторы по regex имени
  --name-fuzzy NAME_FUZZY
                        Нечеткий поиск по имени коннектора (typo-tolerant)
  --table TABLE         Искать по таблицам (source/sink), можно повторять и
                        передавать CSV
  --table-prefix TABLE_PREFIX
                        Искать по prefix таблиц
  --table-suffix TABLE_SUFFIX
                        Искать по suffix таблиц
  --table-regexp TABLE_REGEXP
                        Искать по regex таблиц
  --table-match {any,all}
                        Как матчить несколько значений таблиц: any|all
  --topic TOPIC         Искать по consumed/produced topics, можно повторять и
                        передавать CSV
  --topic-prefix TOPIC_PREFIX
                        Искать по prefix topics
  --topic-suffix TOPIC_SUFFIX
                        Искать по suffix topics
  --topic-regexp TOPIC_REGEXP
                        Искать по regex topics
  --topic-match {any,all}
                        Как матчить несколько значений topics: any|all
  --domain DOMAIN       Фильтр по domain
  --dataset DATASET     Фильтр по dataset
  --type {source,sink}  Фильтр по типу коннектора (source|sink)
  --system SYSTEM       Фильтр по system
  --layer LAYER         Фильтр по layer
  --mode MODE           Фильтр по mode
  --kind KIND           Фильтр по kind
  --host HOST           Искать по db host
  --kafka-bootstrap KAFKA_BOOTSTRAP
                        Искать коннекторы по Kafka bootstrap config values
  --schema-registry-url, --schema-registry SCHEMA_REGISTRY_URL
                        Искать коннекторы по Schema Registry config values
  --database DATABASE   Искать по database / namespace
  --schema SCHEMA       Искать по schema
  --server SERVER       Искать по server-like identifiers
  --has-config-key HAS_CONFIG_KEY
                        Искать где config key существует
  --config-eq CONFIG_EQ
                        Искать по config exact match в формате KEY=VALUE
  --config-prefix CONFIG_PREFIX
                        Искать по config prefix match в формате KEY=VALUE
  --config-suffix CONFIG_SUFFIX
                        Искать по config suffix match в формате KEY=VALUE
  --config-regexp CONFIG_REGEXP
                        Искать по config regex match в формате KEY=REGEX
  --where WHERE         Boolean query: AND/OR/NOT, (), =, !=, ^=, $=, ~=,
                        exists(field), missing(field), config("key")
  --vars VARS           dbt-style vars JSON (object). Можно повторять;
                        мерджится, побеждает последнее.
  --vars-file VARS_FILE
                        Путь к JSON/YAML vars (object). Можно повторять;
                        мерджится. Перебивается --vars.
  --vars-profile VARS_PROFILE
                        Имя профиля из bkkt/vars/profiles/*.yaml. Можно
                        повторять.
```

### `bkkt find --help`

```text
использование: bkkt find [-h] [--source {repo,live,both}] [--env ENV] [--cluster CLUSTER] [--view {short,long}] [--explain {long,stats,none}] [--limit LIMIT] [--ignore-case] [--list-vars] [-y] [--output {text,json,yaml}] [--json] [--jobs JOBS] [--rate-limit-per-second RATE_LIMIT_PER_SECOND] [--name NAME] [--name-prefix NAME_PREFIX] [--name-suffix NAME_SUFFIX] [--name-regexp NAME_REGEXP] [--name-fuzzy NAME_FUZZY] [--table TABLE] [--table-prefix TABLE_PREFIX] [--table-suffix TABLE_SUFFIX] [--table-regexp TABLE_REGEXP] [--table-match {any,all}] [--topic TOPIC] [--topic-prefix TOPIC_PREFIX] [--topic-suffix TOPIC_SUFFIX] [--topic-regexp TOPIC_REGEXP] [--topic-match {any,all}] [--domain DOMAIN] [--dataset DATASET] [--type {source,sink}] [--system SYSTEM] [--layer LAYER] [--mode MODE] [--kind KIND] [--host HOST] [--kafka-bootstrap KAFKA_BOOTSTRAP] [--schema-registry-url SCHEMA_REGISTRY_URL] [--database DATABASE] [--schema SCHEMA] [--server SERVER] [--has-config-key HAS_CONFIG_KEY] [--config-eq CONFIG_EQ] [--config-prefix CONFIG_PREFIX] [--config-suffix CONFIG_SUFFIX] [--config-regexp CONFIG_REGEXP] [--where WHERE] [--vars VARS] [--vars-file VARS_FILE] [--vars-profile VARS_PROFILE]

опции:
  -h, --help            показать эту справку и выйти
  --source {repo,live,both}
                        Где искать коннекторы: repo=отрендеренные manifests,
                        live=Kafka Connect, both=оба источника
  --env ENV             Окружение для поиска: dev|stage|prod|all (по
                        умолчанию: all)
  --cluster CLUSTER     Cluster group filter: <name>|all (по умолчанию: all)
  --view {short,long}   Формат текстового представления: short|long
  --explain {long,stats,none}
                        Explainable search output: long=match paths and
                        related occurrences, stats=compact config statistics
                        by env/cluster, none=legacy match output only
  --limit LIMIT         Ограничить число результатов
  --ignore-case         Игнорировать регистр для exact/prefix/suffix/regex
                        matching
  --list-vars           Показать разрешенные ${...} variables для search
                        filters и выйти
  -y, --yes             Не спрашивать подтверждение для широкого live поиска
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
  --jobs JOBS           Параллелизм (кол-во потоков) для массовых операций. По
                        умолчанию: 8
  --rate-limit-per-second RATE_LIMIT_PER_SECOND
                        Ограничение REST запросов в секунду (RPS) ко всем
                        Connect URL вместе. Если не задано и --jobs > 1,
                        включается безопасный лимит (по умолчанию ~5 RPS). 0 =
                        выключить ограничение.
  --name NAME           Точное совпадение имени коннектора (можно повторять,
                        CSV тоже поддерживается)
  --name-prefix NAME_PREFIX
                        Искать коннекторы по prefix имени
  --name-suffix NAME_SUFFIX
                        Искать коннекторы по suffix имени
  --name-regexp NAME_REGEXP
                        Искать коннекторы по regex имени
  --name-fuzzy NAME_FUZZY
                        Нечеткий поиск по имени коннектора (typo-tolerant)
  --table TABLE         Искать по таблицам (source/sink), можно повторять и
                        передавать CSV
  --table-prefix TABLE_PREFIX
                        Искать по prefix таблиц
  --table-suffix TABLE_SUFFIX
                        Искать по suffix таблиц
  --table-regexp TABLE_REGEXP
                        Искать по regex таблиц
  --table-match {any,all}
                        Как матчить несколько значений таблиц: any|all
  --topic TOPIC         Искать по consumed/produced topics, можно повторять и
                        передавать CSV
  --topic-prefix TOPIC_PREFIX
                        Искать по prefix topics
  --topic-suffix TOPIC_SUFFIX
                        Искать по suffix topics
  --topic-regexp TOPIC_REGEXP
                        Искать по regex topics
  --topic-match {any,all}
                        Как матчить несколько значений topics: any|all
  --domain DOMAIN       Фильтр по domain
  --dataset DATASET     Фильтр по dataset
  --type {source,sink}  Фильтр по типу коннектора (source|sink)
  --system SYSTEM       Фильтр по system
  --layer LAYER         Фильтр по layer
  --mode MODE           Фильтр по mode
  --kind KIND           Фильтр по kind
  --host HOST           Искать по db host
  --kafka-bootstrap KAFKA_BOOTSTRAP
                        Искать коннекторы по Kafka bootstrap config values
  --schema-registry-url, --schema-registry SCHEMA_REGISTRY_URL
                        Искать коннекторы по Schema Registry config values
  --database DATABASE   Искать по database / namespace
  --schema SCHEMA       Искать по schema
  --server SERVER       Искать по server-like identifiers
  --has-config-key HAS_CONFIG_KEY
                        Искать где config key существует
  --config-eq CONFIG_EQ
                        Искать по config exact match в формате KEY=VALUE
  --config-prefix CONFIG_PREFIX
                        Искать по config prefix match в формате KEY=VALUE
  --config-suffix CONFIG_SUFFIX
                        Искать по config suffix match в формате KEY=VALUE
  --config-regexp CONFIG_REGEXP
                        Искать по config regex match в формате KEY=REGEX
  --where WHERE         Boolean query: AND/OR/NOT, (), =, !=, ^=, $=, ~=,
                        exists(field), missing(field), config("key")
  --vars VARS           dbt-style vars JSON (object). Можно повторять;
                        мерджится, побеждает последнее.
  --vars-file VARS_FILE
                        Путь к JSON/YAML vars (object). Можно повторять;
                        мерджится. Перебивается --vars.
  --vars-profile VARS_PROFILE
                        Имя профиля из bkkt/vars/profiles/*.yaml. Можно
                        повторять.
```

### `bkkt lineage --help`

```text
использование: bkkt lineage [-h] [--source {repo,live,both}] [--env ENV] [--cluster CLUSTER] [--ignore-case] [--limit LIMIT] [--kind {auto,connector,topic,table,database,regex,object,topic_or_table}] [--jobs JOBS] [--rate-limit-per-second RATE_LIMIT_PER_SECOND] [--output {text,json,yaml,markdown,mermaid}] object

позиционные аргументы:
  object                Connector name, topic, table, database or regex object

опции:
  -h, --help            показать эту справку и выйти
  --source {repo,live,both}
                        Discovery source: repo, live or both
  --env ENV             Environment scope: dev|stage|prod|all (по умолчанию: all)
  --cluster CLUSTER     Cluster group scope: <name>|all (по умолчанию: all)
  --ignore-case         Case-insensitive matching
  --limit LIMIT         Maximum matched connectors
  --kind {auto,connector,topic,table,database,regex,object,topic_or_table}
                        Optional object kind hint
  --jobs JOBS           Параллелизм (кол-во потоков) для массовых операций. По
                        умолчанию: 8
  --rate-limit-per-second RATE_LIMIT_PER_SECOND
                        Ограничение REST запросов в секунду (RPS) ко всем
                        Connect URL вместе. Если не задано и --jobs > 1,
                        включается безопасный лимит (по умолчанию ~5 RPS). 0 =
                        выключить ограничение.
  --output {text,json,yaml,markdown,mermaid}
                        Output format: text|json|yaml|markdown|mermaid
```

### `bkkt render --help`

```text
использование: bkkt render [-h] [--output {text,json,yaml}] [--json] [--output-file OUTPUT_FILE] [--show-layers] [--config-key CONFIG_KEY] [--include-contracts] [--show-vars] [--no-show-vars] [--vars VARS] [--vars-file VARS_FILE] [--vars-profile VARS_PROFILE] [--no-reuse-overrides] [--reuse-from REUSE_FROM] [--cluster CLUSTER] [--suppress-tag-conflicts] [path] [trace_path]

позиционные аргументы:
  path                  Путь к <env>.*.json манифесту (relative to repo root)
                        или `trace` для bkkt render trace
  trace_path            Manifest path for `bkkt render trace <manifest>`

опции:
  -h, --help            показать эту справку и выйти
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
  --output-file OUTPUT_FILE
                        Записать результат render в файл (формат берётся из
                        --output)
  --show-layers         Печатать список слоёв
  --config-key CONFIG_KEY
                        Config key to explain when using `bkkt render trace`
  --include-contracts   Include typed variable contract metadata in `bkkt
                        render trace` output
  --show-vars           Печатать provenance vars (по умолчанию: включено)
  --no-show-vars        Отключить вывод provenance vars
  --vars VARS           dbt-style vars JSON (object). Можно повторять;
                        мерджится, побеждает последнее значение.
  --vars-file VARS_FILE
                        Путь к JSON/YAML vars (object). Можно повторять;
                        мерджится. Перебивается --vars.
  --vars-profile VARS_PROFILE
                        Имя профиля из bkkt/vars/profiles/*.yaml. Можно
                        повторять; перебивается --vars-file и --vars.
  --no-reuse-overrides  Не применять repo-wide overrides (использовать только
                        base.*.json + env manifest). Полезно для raw-конфигов.
  --reuse-from REUSE_FROM
                        Ограничить набор override-файлов, которые учитываем
                        при render/apply. Можно повторять. Пути relative to
                        repo root.
  --cluster CLUSTER     (опционально) Переопределить cluster group (routing +
                        cluster render policy)
  --suppress-tag-conflicts
                        (опционально) Подавить конфликты тегов (для explain-
                        routing)
```

### `bkkt compare --help`

```text
использование: bkkt compare [-h] [--against {live,connector,file}] [--name NAME] [--file FILE] [--output {text,json,yaml}] [--json] [--show-vars] [--no-show-vars] [--vars VARS] [--vars-file VARS_FILE] [--vars-profile VARS_PROFILE] [--no-reuse-overrides] [--reuse-from REUSE_FROM] [--cluster CLUSTER] [--suppress-tag-conflicts] [--explain-routing] [--no-strict-naming] [--no-policies] path

позиционные аргументы:
  path                  Путь к <env>.*.json манифесту (relative to repo root)

опции:
  -h, --help            показать эту справку и выйти
  --against {live,connector,file}
                        Источник actual-конфига для сравнения (по умолчанию: live)
  --name NAME           Имя live-коннектора для --against connector
  --file FILE           Путь к JSON/YAML config-файлу для --against file
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
  --show-vars           Печатать provenance vars (по умолчанию: включено)
  --no-show-vars        Отключить вывод provenance vars
  --vars VARS           dbt-style vars JSON (object). Можно повторять;
                        мерджится, побеждает последнее значение.
  --vars-file VARS_FILE
                        Путь к JSON/YAML vars (object). Можно повторять;
                        мерджится. Перебивается --vars.
  --vars-profile VARS_PROFILE
                        Имя профиля из bkkt/vars/profiles/*.yaml. Можно
                        повторять.
  --no-reuse-overrides  Не применять repo-wide overrides (использовать только
                        base.*.json + env manifest).
  --reuse-from REUSE_FROM
                        Ограничить набор override-файлов, которые учитываем
                        при render. Можно повторять.
  --cluster CLUSTER     (опционально) Переопределить cluster group (routing +
                        cluster render policy)
  --suppress-tag-conflicts
                        (опционально) Подавить конфликты тегов при routing
  --explain-routing     Показать, как выбран target cluster
  --no-strict-naming    Отключить строгую валидацию нейминга (НЕ
                        рекомендуется). Проверяет dot-style имена и базовые
                        инварианты: env в начале, domain во 2-м сегменте,
                        наличие 'source'/'sink' и system, последний сегмент —
                        числовой индекс, а также (если настроено) правила
                        connectctl.yaml:naming.rules. Подробнее:
                        docs/NAMING.md (или `bkkt help naming`).
  --no-policies         Отключить policy‑проверки окружения (НЕ
                        рекомендуется). Эти проверки ловят потенциально
                        опасные ссылки на чужое окружение (dev/stage/prod) и
                        другие ошибки. Подробнее: docs/POLICIES.md (или `bkkt
                        help policies`).
```

### `bkkt plan --help`

```text
использование: bkkt plan [-h] --env ENV [--base BASE] [--head HEAD] [--output {text,json,yaml}] [--json]

опции:
  -h, --help            показать эту справку и выйти
  --env ENV             Окружение (dev|stage|prod)
  --base BASE           Base git sha (по умолчанию: auto)
  --head HEAD           Head git sha (по умолчанию: auto)
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
```

### `bkkt diff --help`

```text
использование: bkkt diff [-h] --env ENV [--cluster CLUSTER] [--suppress-tag-conflicts] [--changed] [--base BASE] [--head HEAD] [--fail-on-drift] [--max-lines MAX_LINES] [--output {text,json,yaml}] [--json] [--show-vars] [--no-show-vars] [--no-strict-naming] [--no-policies] [--vars VARS] [--vars-file VARS_FILE] [--vars-profile VARS_PROFILE] [paths ...]

позиционные аргументы:
  paths                 Явные manifest paths для diff (если не указано и нет
                        --changed, diff по всему env)

опции:
  -h, --help            показать эту справку и выйти
  --env ENV             Окружение (dev|stage|prod)
  --cluster CLUSTER     Имя группы кластеров (cluster group). Если задано —
                        принудительно использовать этот кластер для всех
                        коннекторов. Если не задано — кластер выбирается через
                        routing (connectctl.cluster/tags/default_cluster).
  --suppress-tag-conflicts
                        Если несколько тегов задают один и тот же параметр
                        разными значениями: вывести warning и взять значение
                        последнего тега. Параметры из
                        tags.hard_conflict_params всегда приводят к ошибке.
  --changed             Diff только коннекторы, затронутые git diff
  --base BASE           Base git sha (по умолчанию: auto)
  --head HEAD           Head git sha (по умолчанию: HEAD)
  --fail-on-drift       Возвращать ненулевой exit code, если найден drift
  --max-lines MAX_LINES
                        Максимум строк diff на коннектор в отчёте (по умолчанию:
                        200)
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
  --show-vars           Печатать provenance vars на коннектор (по умолчанию:
                        включено)
  --no-show-vars        Отключить вывод provenance vars
  --no-strict-naming    Отключить строгую валидацию нейминга (НЕ
                        рекомендуется). Проверяет dot-style имена и базовые
                        инварианты: env в начале, domain во 2-м сегменте,
                        наличие 'source'/'sink' и system, последний сегмент —
                        числовой индекс, а также (если настроено) правила
                        connectctl.yaml:naming.rules. Подробнее:
                        docs/NAMING.md (или `bkkt help naming`).
  --no-policies         Отключить policy‑проверки окружения (НЕ
                        рекомендуется). Эти проверки ловят потенциально
                        опасные ссылки на чужое окружение (dev/stage/prod) и
                        другие ошибки. Подробнее: docs/POLICIES.md (или `bkkt
                        help policies`).
  --vars VARS           dbt-style vars JSON (object). Можно повторять;
                        мерджится, побеждает последнее.
  --vars-file VARS_FILE
                        Путь к JSON/YAML vars (object). Можно повторять;
                        мерджится. Перебивается --vars.
  --vars-profile VARS_PROFILE
                        Имя профиля из bkkt/vars/profiles/*.yaml. Можно
                        повторять.
```

### `bkkt drift --help`

```text
использование: bkkt drift [-h] --env {dev,stage,prod} [--cluster CLUSTER] [--clusters [CLUSTERS]] [--changed] [--base BASE] [--head HEAD] [--include-diffs] [--max-lines MAX_LINES] [--top TOP] [--output {text,json,yaml}] [--json] [--output-file OUTPUT_FILE] [--fail-on-drift] [--no-strict-naming] [--no-policies] [-y] [paths ...]

позиционные аргументы:
  paths                 Опционально: manifest paths (repo-relative), чтобы
                        ограничить область проверки

опции:
  -h, --help            показать эту справку и выйти
  --env {dev,stage,prod}
                        Target environment
  --cluster CLUSTER     Имя группы кластеров (cluster group). Если не задано —
                        используется default_cluster.
  --clusters [CLUSTERS]
                        Проверять drift по набору cluster groups без override.
                        Укажите список через запятую или используйте
                        --clusters all. Нельзя использовать вместе с
                        --cluster.
  --changed             Проверять только манифесты, затронутые git diff
                        (base..head)
  --base BASE           Base git SHA для --changed (по умолчанию: auto)
  --head HEAD           Head git SHA для --changed (по умолчанию: HEAD)
  --include-diffs       Включить unified diff для drifted connectors
  --max-lines MAX_LINES
                        Максимум строк diff на один коннектор (когда
                        --include-diffs)
  --top TOP             Сколько top drift reasons вывести (по ключам конфига)
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
  --output-file OUTPUT_FILE
                        Записать markdown в файл
  --fail-on-drift       Exit code != 0 если найден drift/missing
  --no-strict-naming    Отключить строгую валидацию нейминга (НЕ
                        рекомендуется). Проверяет dot-style имена и базовые
                        инварианты: env в начале, domain во 2-м сегменте,
                        наличие 'source'/'sink' и system, последний сегмент —
                        числовой индекс, а также (если настроено) правила
                        connectctl.yaml:naming.rules. Подробнее:
                        docs/NAMING.md (или `bkkt help naming`).
  --no-policies         Отключить policy‑проверки окружения (НЕ
                        рекомендуется). Эти проверки ловят потенциально
                        опасные ссылки на чужое окружение (dev/stage/prod) и
                        другие ошибки. Подробнее: docs/POLICIES.md (или `bkkt
                        help policies`).
  -y, --yes             Не спрашивать подтверждение для широкого multi-cluster
                        drift
```

### `bkkt get-connector --help`

```text
использование: bkkt get-connector [-h] --env ENV [--cluster CLUSTER] [--output {text,json,yaml}] [--json] [--status {none,short,long}] [--raw-status-json] [--meta] name

позиционные аргументы:
  name                  Имя коннектора

опции:
  -h, --help            показать эту справку и выйти
  --env ENV             Целевое окружение (dev|stage|prod)
  --cluster CLUSTER     Имя группы кластеров (cluster group), либо all/* для
                        fan-out. По умолчанию: default_cluster из
                        connectctl.yaml
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
  --status {none,short,long}
                        none=только config, short=краткий статус,
                        long=подробный статус (tasks/trace); raw — по флагу
  --raw-status-json     (опционально) В режиме --status long дополнительно
                        включить raw JSON статуса (как вернул Kafka Connect)
  --meta                Показать метаданные, распарсенные из имени коннектора
```

### `bkkt apply --help`

```text
использование: bkkt apply [-h] --env ENV [--state-db STATE_DB] [--no-audit] [--cluster CLUSTER] [--suppress-tag-conflicts] [--changed] [--base BASE] [--head HEAD] [--dry-run] [--runtime-unsafe-rest] [--schema-preflight | --no-schema-preflight] [--schema-preflight-reason SCHEMA_PREFLIGHT_REASON] [--vars-preflight | --no-vars-preflight] [--vars-preflight-reason VARS_PREFLIGHT_REASON] [--vars-preflight-provider-contract VARS_PREFLIGHT_PROVIDER_CONTRACT] [--vars-preflight-secret-index VARS_PREFLIGHT_SECRET_INDEX] [--failure-bundle-dir FAILURE_BUNDLE_DIR] [--jobs JOBS] [--rate-limit-per-second RATE_LIMIT_PER_SECOND] [--connect-validate] [--no-connect-validate] [--rollback-on-fail] [--no-rollback-on-fail] [--health-gates] [--post-smoke] [--wait-seconds WAIT_SECONDS] [--wait-timeout-seconds TIMEOUT_SECONDS] [--timeout-seconds TIMEOUT_SECONDS] [--poll-interval-seconds POLL_INTERVAL_SECONDS] [--expand-templates] [--show-vars] [--no-show-vars] [--vars VARS] [--vars-file VARS_FILE] [--vars-profile VARS_PROFILE] [--no-reuse-overrides] [--reuse-from REUSE_FROM] [--print-config] [--no-print-config] [--no-strict-naming] [--no-policies] [--no-skip-if-unchanged] [--force] [--drop-if-exists] [--drop-if-failed] [--from-rendered FROM_RENDERED] [--artifact-strict] [--no-auto-catalog] [--no-smoke] [--smoke-strict] [paths ...]

позиционные аргументы:
  paths                 Явные пути к манифестам для apply (если не указан
                        --changed)

опции:
  -h, --help            показать эту справку и выйти
  --env ENV             Окружение (dev|stage|prod)
  --state-db STATE_DB   Path to BKKT SQLite state DB. Defaults to
                        .bkkt/state/bkkt.sqlite or BKKT_STATE_DB.
  --no-audit            Disable local SQLite audit write for this command.
  --cluster CLUSTER     Имя группы кластеров (cluster group). По умолчанию:
                        default_cluster из connectctl.yaml
  --suppress-tag-conflicts
                        Если несколько тегов задают один и тот же параметр
                        разными значениями: вывести warning и взять значение
                        последнего тега. Параметры из
                        tags.hard_conflict_params всегда приводят к ошибке.
  --changed             Применить только коннекторы, затронутые git diff
  --base BASE           Base git sha (по умолчанию: auto)
  --head HEAD           Head git sha (по умолчанию: auto)
  --dry-run             Режим без изменений: не вызывать Kafka Connect API
  --runtime-unsafe-rest
                        Break-glass: allow raw Kafka Connect REST mutations
                        for operator-managed runtimes (Strimzi/CFK). Prefer
                        CRD/GitOps mutation instead.
  --schema-preflight, --no-schema-preflight
                        Run Schema Registry risk preflight before live upsert.
                        --no-schema-preflight is break-glass and requires
                        --schema-preflight-reason.
  --schema-preflight-reason SCHEMA_PREFLIGHT_REASON
                        Required audit reason when using --no-schema-
                        preflight.
  --vars-preflight, --no-vars-preflight
                        Run deploy-context vars/provider/secret preflight
                        before apply. --no-vars-preflight is break-glass and
                        requires --vars-preflight-reason.
  --vars-preflight-reason VARS_PREFLIGHT_REASON
                        Required audit reason when using --no-vars-preflight.
  --vars-preflight-provider-contract VARS_PREFLIGHT_PROVIDER_CONTRACT
                        Provider contract YAML file or directory. Can be
                        repeated. По умолчанию:
                        bkkt/var_providers/contracts/**/*.yaml.
  --vars-preflight-secret-index VARS_PREFLIGHT_SECRET_INDEX
                        Optional YAML index of allowed external secret refs
                        for exact preflight without fetching secret values.
  --failure-bundle-dir FAILURE_BUNDLE_DIR
                        Каталог для diagnostic failure bundles. При ошибке
                        BKKT сохранит prepared manifest, routing и error
                        payload в отдельный подкаталог (по умолчанию:
                        artifacts/failure-bundles/apply).
  --jobs JOBS           Параллелизм (кол-во потоков) для массовых операций. По
                        умолчанию: 1 (последовательно)
  --rate-limit-per-second RATE_LIMIT_PER_SECOND
                        Ограничение REST запросов в секунду (RPS) ко всем
                        Connect URL вместе. Если не задано и --jobs > 1,
                        включается безопасный лимит (по умолчанию ~5 RPS). 0 =
                        выключить ограничение.
  --connect-validate    Проверять конфиг через Kafka Connect validate endpoint
                        перед upsert (по умолчанию: включено)
  --no-connect-validate
                        Пропустить валидацию конфига через Kafka Connect (НЕ
                        рекомендуется)
  --rollback-on-fail    Откатывать на предыдущий конфиг при ошибке deploy (по
                        умолчанию: включено на stage/prod)
  --no-rollback-on-fail
                        Выключить откат при ошибке
  --health-gates        Operator UX alias: enforce validate + wait healthy +
                        smoke checks (safe no-op if those defaults are already
                        enabled)
  --post-smoke          Run post-deploy smoke checks (alias for default smoke
                        behavior)
  --wait-seconds WAIT_SECONDS
                        Пауза после deploy перед опросом статуса (сек.)
  --wait-timeout-seconds TIMEOUT_SECONDS
                        Alias for --timeout-seconds
  --timeout-seconds TIMEOUT_SECONDS
                        Общий таймаут ожидания статуса (сек.)
  --poll-interval-seconds POLL_INTERVAL_SECONDS
                        Интервал опроса статуса (сек.)
  --expand-templates    Включить template-aware apply: разворачивать
                        template‑манифесты с ${...} в имени файла, используя
                        instances (prod.instances.json/instances.json) или
                        vars.index/vars.instances. Также пытается резолвить
                        отсутствующие запрошенные instance‑файлы: находит
                        подходящий template и извлекает vars из имени файла.
  --show-vars           Печатать provenance vars для каждого применяемого
                        коннектора (по умолчанию: включено)
  --no-show-vars        Не показывать provenance vars
  --vars VARS           dbt-style vars JSON (object). Можно повторять;
                        мерджится, побеждает последнее.
  --vars-file VARS_FILE
                        Путь к JSON/YAML файлу с vars (object). Можно
                        повторять; мерджится. Значения из --vars имеют
                        приоритет.
  --vars-profile VARS_PROFILE
                        Имя профиля из bkkt/vars/profiles/*.yaml. Можно
                        повторять.
  --no-reuse-overrides  Не применять repo-wide overrides (использовать только
                        base.*.json + env manifest). Полезно для raw-конфигов.
  --reuse-from REUSE_FROM
                        Ограничить набор override-файлов, которые учитываем
                        при apply/render. Можно повторять. Пути relative to
                        repo root.
  --print-config        Печатать итоговый конфиг каждого коннектора перед
                        apply (по умолчанию: включено)
  --no-print-config     Не печатать итоговый конфиг коннекторов
  --no-strict-naming    Отключить строгую валидацию нейминга (НЕ
                        рекомендуется). Проверяет dot-style имена и базовые
                        инварианты: env в начале, domain во 2-м сегменте,
                        наличие 'source'/'sink' и system, последний сегмент —
                        числовой индекс, а также (если настроено) правила
                        connectctl.yaml:naming.rules. Подробнее:
                        docs/NAMING.md (или `bkkt help naming`).
  --no-policies         Отключить policy‑проверки окружения (НЕ
                        рекомендуется). Эти проверки ловят потенциально
                        опасные ссылки на чужое окружение (dev/stage/prod) и
                        другие ошибки. Подробнее: docs/POLICIES.md (или `bkkt
                        help policies`).
  --no-skip-if-unchanged
                        Выключить skip-if-unchanged (drift-skip) и всегда
                        делать upsert
  --force               Форсировать upsert даже если конфиг не изменился
  --drop-if-exists      Удалить коннектор перед apply, если он уже существует
                        (ОПАСНО)
  --drop-if-failed      Если deploy упал и коннектор оказался в FAILED —
                        удалить его (по умолчанию: выключено)
  --from-rendered FROM_RENDERED
                        Каталог с заранее отрендеренными JSON артефактами
                        коннекторов
  --artifact-strict     При использовании --from-rendered: упасть, если
                        отсутствует хотя бы один артефакт (CI-safe)
  --no-auto-catalog     Выключить авто‑создание баз данных AWS Glue для
                        Iceberg sinks
  --no-smoke            Выключить smoke checks Kafka (наличие топиков / lag
                        для sink)
  --smoke-strict        Завершать команду ошибкой, если smoke checks нашли
                        проблемы
```

### `bkkt export --help`

```text
использование: bkkt export [-h] --env ENV [--cluster CLUSTER] [--all] [--type {source,sink}] [--domain DOMAIN] [--system SYSTEM] [--connector-dir CONNECTOR_DIR] [--auto-index-suffix-on-collision] [--no-auto-index-suffix-on-collision] [--regexp REGEXP] [--dry-run] [--force] [--jobs JOBS] [--rate-limit-per-second RATE_LIMIT_PER_SECOND] [--reuse-overrides] [--no-reuse-overrides] [--save-diffs] [--reuse-from REUSE_FROM] [--modes MODES] [--init-only] [--kinds KINDS] [--as-name AS_NAMES] [--iceberg-generate-kinds ICEBERG_GENERATE_KINDS] [--iceberg-table-id-columns ICEBERG_TABLE_ID_COLUMNS] [--iceberg-generate-overrides] [--no-iceberg-generate-overrides] [--iceberg-generate-manifests] [--no-iceberg-generate-manifests] [--vars VARS] [--vars-file VARS_FILE] [--vars-profile VARS_PROFILE] [names ...]

позиционные аргументы:
  names                 Имена коннекторов для экспорта (игнорируется с --all)

опции:
  -h, --help            показать эту справку и выйти
  --env ENV             Окружение/кластер, из которого экспортируем
                        (dev|stage|prod)
  --cluster CLUSTER     Имя cluster group, из которого экспортируем (по
                        умолчанию: default_cluster из connectctl.yaml)
  --all                 Экспортировать все коннекторы из кластера
  --type {source,sink}  Фильтр по типу коннектора (в основном вместе с --all)
  --domain DOMAIN       Домен (переопределение размещения для явных имен;
                        фильтр для --all)
  --system SYSTEM       Система (переопределение размещения для явных имен;
                        фильтр для --all)
  --connector-dir CONNECTOR_DIR
                        connector_dir (переопределение размещения для явных
                        имен)
  --auto-index-suffix-on-collision
                        Если sink export конфликтует с существующим путём в
                        repo (одно и то же размещение), автоматически дописать
                        к connector_dir суффикс __<index> (по умолчанию:
                        включено)
  --no-auto-index-suffix-on-collision
                        Выключить автоматическое суффиксирование __<index> при
                        коллизиях sink export
  --regexp REGEXP       Экспортировать только коннекторы, где regexp матчится
                        по имени или JSON конфигу (можно повторять)
  --dry-run             Режим без изменений: не писать файлы, только показать
                        действия
  --force               Перезаписать существующие файлы
  --jobs JOBS           Параллелизм (кол-во потоков) для массовых операций. По
                        умолчанию: 1 (последовательно)
  --rate-limit-per-second RATE_LIMIT_PER_SECOND
                        Ограничение REST запросов в секунду (RPS) ко всем
                        Connect URL вместе. Если не задано и --jobs > 1,
                        включается безопасный лимит (по умолчанию ~5 RPS). 0 =
                        выключить ограничение.
  --reuse-overrides     Пытаться минимизировать экспорт, переиспользуя repo
                        overrides (по умолчанию: включено)
  --no-reuse-overrides  Не переиспользовать overrides; записать сырой конфиг в
                        env manifest (точная копия)
  --save-diffs          В режиме reuse_overrides (режим по умолчанию)
                        сохранять значения из кластера даже если в repo есть
                        override (дописать их в экспортированные манифесты) и
                        записать diffs override-vs-remote в
                        connector_dir/export/. По умолчанию: false
                        (предпочитать repo overrides и опускать перекрытые
                        ключи).
  --reuse-from REUSE_FROM
                        Ограничить reuse overrides: использовать только эти
                        override файлы как baseline (можно повторять)
  --modes MODES         Для source export: дополнительно сгенерировать эти
                        modes (через запятую, можно повторять). Встроенные:
                        cdc, init (алиасы: stream->cdc, initial->init). Можно
                        указывать свои modes (например backfill) — будут
                        созданы modes/<mode>/* и name variants. Пример:
                        --modes init,cdc
  --init-only           Для source export: создать modes/init/all.json с
                        debezium_snapshot_mode_init=initial_only. Также
                        автоматически добавляет 'init' в --modes, если забыли.
  --kinds KINDS         Для sink export: дополнительно сгенерировать эти kinds
                        (через запятую, можно повторять). Kind попадает в имя
                        как '.cdc.<kind>.' и включает overlays
                        'types/<kind>/*'. Для iceberg часто используются:
                        events, flatten, raw, ods, default (но список не
                        ограничен). Пример: --kinds events,flatten
  --as-name AS_NAMES    Переопределить имя коннектора в репозитории при export
                        (удобно для миграции/нормализации). Поддерживаемые
                        форматы (можно повторять): 1) --as-name <new_name>
                        (если экспортируется ровно 1 коннектор); 2) --as-name
                        <remote>=<new> (явное сопоставление); 3) для N
                        коннекторов: N раз --as-name <new_name> (по порядку).
  --iceberg-generate-kinds ICEBERG_GENERATE_KINDS
                        Для Iceberg sinks: дополнительно сгенерировать
                        manifests/overrides для этих kinds (через запятую,
                        можно повторять). Пример: --iceberg-generate-kinds
                        events,flatten
  --iceberg-table-id-columns ICEBERG_TABLE_ID_COLUMNS
                        Для Iceberg flatten scaffolding: задать id-columns
                        mapping на таблицу в виде <table>=<col1,col2,...>.
                        Можно повторять.
  --iceberg-generate-overrides
                        При использовании --iceberg-generate-kinds: также
                        генерировать overrides types/<kind>/all.json (по
                        умолчанию: включено)
  --no-iceberg-generate-overrides
                        Выключить генерацию overrides types/<kind>/all.json
                        (только manifests)
  --iceberg-generate-manifests
                        При использовании --iceberg-generate-kinds: также
                        генерировать env manifests для запрошенных kinds (по
                        умолчанию: включено)
  --no-iceberg-generate-manifests
                        Выключить генерацию env manifests (только overrides)
  --vars VARS           dbt-style vars JSON (object). Можно повторять;
                        мерджится, побеждает последнее.
  --vars-file VARS_FILE
                        Путь к JSON/YAML файлу с vars (object). Можно
                        повторять; мерджится. Перебивается --vars.
  --vars-profile VARS_PROFILE
                        Имя профиля из bkkt/vars/profiles/*.yaml. Можно
                        повторять.
```

### `bkkt reconcile --help`

```text
использование: bkkt reconcile [-h] [--source {live}] --env ENV [--cluster CLUSTER] [--names NAMES] [--regexp REGEXP] [--domain DOMAIN] [--system SYSTEM] [--connector-dir CONNECTOR_DIR] [--raw] [--dry-run] [--write] [--force] [--output {markdown,json,yaml}] [--ignore-case] [--limit LIMIT] [--jobs JOBS] [--rate-limit-per-second RATE_LIMIT_PER_SECOND]

опции:
  -h, --help            показать эту справку и выйти
  --source {live}
  --env ENV             Source environment
  --cluster CLUSTER     Source cluster group
  --names NAMES         Connector name(s), repeatable or CSV
  --regexp REGEXP       Resolve live connector names by regex
  --domain DOMAIN       Export placement override
  --system SYSTEM       Export placement override
  --connector-dir CONNECTOR_DIR
                        Export placement override
  --raw                 Export raw configs without reuse-overrides
                        minimization
  --dry-run             Do not write files (default unless --write is set)
  --write               Write planned files into the repo
  --force               Overwrite existing files
  --output {markdown,json,yaml}
  --ignore-case
  --limit LIMIT
  --jobs JOBS           Параллелизм (кол-во потоков) для массовых операций. По
                        умолчанию: 8
  --rate-limit-per-second RATE_LIMIT_PER_SECOND
                        Ограничение REST запросов в секунду (RPS) ко всем
                        Connect URL вместе. Если не задано и --jobs > 1,
                        включается безопасный лимит (по умолчанию ~5 RPS). 0 =
                        выключить ограничение.
```

### `bkkt kafka --help`

```text
использование: bkkt kafka [-h] {topics,groups,brokers} ...

позиционные аргументы:
  {topics,groups,brokers}
    topics              Kafka topics inventory
    groups              Kafka consumer groups inventory
    brokers             Kafka broker and cluster inventory

опции:
  -h, --help            показать эту справку и выйти
```

#### `bkkt kafka topics --help`

```text
использование: bkkt kafka topics [-h] {list,describe,plan,apply} ...

позиционные аргументы:
  {list,describe,plan,apply}
    list                List Kafka topics
    describe            Describe one Kafka topic
    plan                Plan Kafka topic GitOps changes
    apply               Apply Kafka topic GitOps changes

опции:
  -h, --help            показать эту справку и выйти
```

##### `bkkt kafka topics list --help`

```text
использование: bkkt kafka topics list [-h] --env ENV [--cluster CLUSTER] [--bootstrap-server BOOTSTRAP_SERVER] [--output {text,json,yaml}] [--json] [--prefix PREFIX] [--regexp REGEXP] [--limit LIMIT] [--include-internal] [--with-offsets]

опции:
  -h, --help            показать эту справку и выйти
  --env ENV             Target env: dev|stage|prod
  --cluster CLUSTER     Cluster group. Defaults to default_cluster from
                        connectctl.yaml
  --bootstrap-server BOOTSTRAP_SERVER
                        Explicit Kafka bootstrap override for admin
                        diagnostics. Comma-separated values are accepted.
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
  --prefix PREFIX       Filter names by prefix
  --regexp REGEXP       Filter names by regex
  --limit LIMIT         Max rows, по умолчанию: 500
  --include-internal    Include internal topics such as __consumer_offsets
  --with-offsets        Also calculate partition and end-offset summary for
                        selected topics
```

##### `bkkt kafka topics describe --help`

```text
использование: bkkt kafka topics describe [-h] --env ENV [--cluster CLUSTER] [--bootstrap-server BOOTSTRAP_SERVER] [--output {text,json,yaml}] [--json] [--no-offsets] topic

позиционные аргументы:
  topic                 Topic name

опции:
  -h, --help            показать эту справку и выйти
  --env ENV             Target env: dev|stage|prod
  --cluster CLUSTER     Cluster group. Defaults to default_cluster from
                        connectctl.yaml
  --bootstrap-server BOOTSTRAP_SERVER
                        Explicit Kafka bootstrap override for admin
                        diagnostics. Comma-separated values are accepted.
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
  --no-offsets          Skip beginning/end offset lookup
```

##### `bkkt kafka topics plan --help`

```text
использование: bkkt kafka topics plan [-h] --env ENV [--cluster CLUSTER] [--bootstrap-server BOOTSTRAP_SERVER] [--output {text,json,yaml}] [--json] --file FILE

опции:
  -h, --help            показать эту справку и выйти
  --env ENV             Target env: dev|stage|prod
  --cluster CLUSTER     Cluster group. Defaults to default_cluster from
                        connectctl.yaml
  --bootstrap-server BOOTSTRAP_SERVER
                        Explicit Kafka bootstrap override for admin
                        diagnostics. Comma-separated values are accepted.
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
  --file FILE           Kafka topic manifest file or directory; can be passed
                        multiple times
```

##### `bkkt kafka topics apply --help`

```text
использование: bkkt kafka topics apply [-h] --env ENV [--cluster CLUSTER] [--bootstrap-server BOOTSTRAP_SERVER] [--output {text,json,yaml}] [--json] --file FILE [--dry-run] [--yes]

опции:
  -h, --help            показать эту справку и выйти
  --env ENV             Target env: dev|stage|prod
  --cluster CLUSTER     Cluster group. Defaults to default_cluster from
                        connectctl.yaml
  --bootstrap-server BOOTSTRAP_SERVER
                        Explicit Kafka bootstrap override for admin
                        diagnostics. Comma-separated values are accepted.
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
  --file FILE           Kafka topic manifest file or directory; can be passed
                        multiple times
  --dry-run             Only print the plan
  --yes, -y             Confirm live mutation
```

#### `bkkt kafka groups --help`

```text
использование: bkkt kafka groups [-h] {list,describe,lag} ...

позиционные аргументы:
  {list,describe,lag}
    list               List Kafka consumer groups
    describe           Describe one Kafka consumer group
    lag                Show lag for one Kafka consumer group

опции:
  -h, --help           показать эту справку и выйти
```

##### `bkkt kafka groups list --help`

```text
использование: bkkt kafka groups list [-h] --env ENV [--cluster CLUSTER] [--bootstrap-server BOOTSTRAP_SERVER] [--output {text,json,yaml}] [--json] [--prefix PREFIX] [--regexp REGEXP] [--limit LIMIT]

опции:
  -h, --help            показать эту справку и выйти
  --env ENV             Target env: dev|stage|prod
  --cluster CLUSTER     Cluster group. Defaults to default_cluster from
                        connectctl.yaml
  --bootstrap-server BOOTSTRAP_SERVER
                        Explicit Kafka bootstrap override for admin
                        diagnostics. Comma-separated values are accepted.
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
  --prefix PREFIX       Filter names by prefix
  --regexp REGEXP       Filter names by regex
  --limit LIMIT         Max rows, по умолчанию: 500
```

##### `bkkt kafka groups describe --help`

```text
использование: bkkt kafka groups describe [-h] --env ENV [--cluster CLUSTER] [--bootstrap-server BOOTSTRAP_SERVER] [--output {text,json,yaml}] [--json] [--topic TOPIC] group

позиционные аргументы:
  group                 Consumer group id

опции:
  -h, --help            показать эту справку и выйти
  --env ENV             Target env: dev|stage|prod
  --cluster CLUSTER     Cluster group. Defaults to default_cluster from
                        connectctl.yaml
  --bootstrap-server BOOTSTRAP_SERVER
                        Explicit Kafka bootstrap override for admin
                        diagnostics. Comma-separated values are accepted.
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
  --topic TOPIC         Optional comma-separated topic filter
```

##### `bkkt kafka groups lag --help`

```text
использование: bkkt kafka groups lag [-h] --env ENV [--cluster CLUSTER] [--bootstrap-server BOOTSTRAP_SERVER] [--output {text,json,yaml}] [--json] [--topic TOPIC] group

позиционные аргументы:
  group                 Consumer group id

опции:
  -h, --help            показать эту справку и выйти
  --env ENV             Target env: dev|stage|prod
  --cluster CLUSTER     Cluster group. Defaults to default_cluster from
                        connectctl.yaml
  --bootstrap-server BOOTSTRAP_SERVER
                        Explicit Kafka bootstrap override for admin
                        diagnostics. Comma-separated values are accepted.
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
  --topic TOPIC         Optional comma-separated topic filter
```

#### `bkkt kafka brokers --help`

```text
использование: bkkt kafka brokers [-h] {describe,health} ...

позиционные аргументы:
  {describe,health}
    describe         Describe Kafka brokers
    health           Read-only Kafka broker health summary

опции:
  -h, --help         показать эту справку и выйти
```

##### `bkkt kafka brokers describe --help`

```text
использование: bkkt kafka brokers describe [-h] --env ENV [--cluster CLUSTER] [--bootstrap-server BOOTSTRAP_SERVER] [--output {text,json,yaml}] [--json] [--configs]

опции:
  -h, --help            показать эту справку и выйти
  --env ENV             Target env: dev|stage|prod
  --cluster CLUSTER     Cluster group. Defaults to default_cluster from
                        connectctl.yaml
  --bootstrap-server BOOTSTRAP_SERVER
                        Explicit Kafka bootstrap override for admin
                        diagnostics. Comma-separated values are accepted.
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
  --configs             Best-effort broker config lookup
```

##### `bkkt kafka brokers health --help`

```text
использование: bkkt kafka brokers health [-h] --env ENV [--cluster CLUSTER] [--bootstrap-server BOOTSTRAP_SERVER] [--output {text,json,yaml}] [--json]

опции:
  -h, --help            показать эту справку и выйти
  --env ENV             Target env: dev|stage|prod
  --cluster CLUSTER     Cluster group. Defaults to default_cluster from
                        connectctl.yaml
  --bootstrap-server BOOTSTRAP_SERVER
                        Explicit Kafka bootstrap override for admin
                        diagnostics. Comma-separated values are accepted.
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
```

### `bkkt schema --help`

```text
использование: bkkt schema [-h] {subjects,compatibility,impact,plan,preflight,register} ...

позиционные аргументы:
  {subjects,compatibility,impact,plan,preflight,register}
    subjects            Schema Registry subjects
    compatibility       Schema Registry compatibility checks
    impact              Infer topic/search impact for a Schema Registry
                        subject
    plan                Plan schema evolution impact before registering a
                        version
    preflight           Analyze schema-affecting connector config changes
                        before deploy
    register            Register a new schema version with guarded dry-run/yes
                        flow

опции:
  -h, --help            показать эту справку и выйти
```

#### `bkkt schema subjects --help`

```text
использование: bkkt schema subjects [-h] {list,versions,describe,diff} ...

позиционные аргументы:
  {list,versions,describe,diff}
    list                List Schema Registry subjects
    versions            List subject versions
    describe            Describe a subject or version
    diff                Diff two subject versions

опции:
  -h, --help            показать эту справку и выйти
```

##### `bkkt schema subjects list --help`

```text
использование: bkkt schema subjects list [-h] --env ENV [--cluster CLUSTER] [--url URL] [--timeout-seconds TIMEOUT_SECONDS] [--output {text,json,yaml}] [--json] [--prefix PREFIX] [--regexp REGEXP] [--limit LIMIT]

опции:
  -h, --help            показать эту справку и выйти
  --env ENV             Target env: dev|stage|prod
  --cluster CLUSTER     Cluster group. Defaults to default_cluster from
                        connectctl.yaml
  --url URL             Override Schema Registry URL(s), comma-separated
  --timeout-seconds TIMEOUT_SECONDS
                        Schema Registry request timeout, по умолчанию: config value
                        or 10
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
  --prefix PREFIX       Filter subjects by prefix
  --regexp REGEXP       Filter subjects by regex
  --limit LIMIT         Max rows, по умолчанию: 500
```

##### `bkkt schema subjects versions --help`

```text
использование: bkkt schema subjects versions [-h] --env ENV [--cluster CLUSTER] [--url URL] [--timeout-seconds TIMEOUT_SECONDS] [--output {text,json,yaml}] [--json] subject

позиционные аргументы:
  subject               Schema Registry subject

опции:
  -h, --help            показать эту справку и выйти
  --env ENV             Target env: dev|stage|prod
  --cluster CLUSTER     Cluster group. Defaults to default_cluster from
                        connectctl.yaml
  --url URL             Override Schema Registry URL(s), comma-separated
  --timeout-seconds TIMEOUT_SECONDS
                        Schema Registry request timeout, по умолчанию: config value
                        or 10
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
```

##### `bkkt schema subjects describe --help`

```text
использование: bkkt schema subjects describe [-h] --env ENV [--cluster CLUSTER] [--url URL] [--timeout-seconds TIMEOUT_SECONDS] [--output {text,json,yaml}] [--json] [--version VERSION] subject

позиционные аргументы:
  subject               Schema Registry subject

опции:
  -h, --help            показать эту справку и выйти
  --env ENV             Target env: dev|stage|prod
  --cluster CLUSTER     Cluster group. Defaults to default_cluster from
                        connectctl.yaml
  --url URL             Override Schema Registry URL(s), comma-separated
  --timeout-seconds TIMEOUT_SECONDS
                        Schema Registry request timeout, по умолчанию: config value
                        or 10
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
  --version VERSION     Optional version to fetch, по умолчанию: subject summary
                        with latest
```

##### `bkkt schema subjects diff --help`

```text
использование: bkkt schema subjects diff [-h] --env ENV [--cluster CLUSTER] [--url URL] [--timeout-seconds TIMEOUT_SECONDS] [--output {text,json,yaml}] [--json] --from-version FROM_VERSION [--to-version TO_VERSION] subject

позиционные аргументы:
  subject               Schema Registry subject

опции:
  -h, --help            показать эту справку и выйти
  --env ENV             Target env: dev|stage|prod
  --cluster CLUSTER     Cluster group. Defaults to default_cluster from
                        connectctl.yaml
  --url URL             Override Schema Registry URL(s), comma-separated
  --timeout-seconds TIMEOUT_SECONDS
                        Schema Registry request timeout, по умолчанию: config value
                        or 10
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
  --from-version FROM_VERSION
                        Base schema version
  --to-version TO_VERSION
                        Target schema version
```

#### `bkkt schema compatibility --help`

```text
использование: bkkt schema compatibility [-h] {get,check,set} ...

позиционные аргументы:
  {get,check,set}
    get            Get global or subject compatibility
    check          Check schema compatibility
    set            Set global or subject compatibility with guarded dry-
                   run/yes flow

опции:
  -h, --help       показать эту справку и выйти
```

##### `bkkt schema compatibility get --help`

```text
использование: bkkt schema compatibility get [-h] --env ENV [--cluster CLUSTER] [--url URL] [--timeout-seconds TIMEOUT_SECONDS] [--output {text,json,yaml}] [--json] [--subject SUBJECT]

опции:
  -h, --help            показать эту справку и выйти
  --env ENV             Target env: dev|stage|prod
  --cluster CLUSTER     Cluster group. Defaults to default_cluster from
                        connectctl.yaml
  --url URL             Override Schema Registry URL(s), comma-separated
  --timeout-seconds TIMEOUT_SECONDS
                        Schema Registry request timeout, по умолчанию: config value
                        or 10
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
  --subject SUBJECT     Optional subject
```

##### `bkkt schema compatibility check --help`

```text
использование: bkkt schema compatibility check [-h] --env ENV [--cluster CLUSTER] [--url URL] [--timeout-seconds TIMEOUT_SECONDS] [--output {text,json,yaml}] [--json] --schema-file SCHEMA_FILE [--version VERSION] [--schema-type {AVRO,PROTOBUF,JSON}] subject

позиционные аргументы:
  subject               Schema Registry subject

опции:
  -h, --help            показать эту справку и выйти
  --env ENV             Target env: dev|stage|prod
  --cluster CLUSTER     Cluster group. Defaults to default_cluster from
                        connectctl.yaml
  --url URL             Override Schema Registry URL(s), comma-separated
  --timeout-seconds TIMEOUT_SECONDS
                        Schema Registry request timeout, по умолчанию: config value
                        or 10
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
  --schema-file SCHEMA_FILE
                        Schema file to validate
  --version VERSION     Version to check against, по умолчанию: latest
  --schema-type {AVRO,PROTOBUF,JSON}
                        Optional schema type override
```

##### `bkkt schema compatibility set --help`

```text
использование: bkkt schema compatibility set [-h] --env ENV [--cluster CLUSTER] [--url URL] [--timeout-seconds TIMEOUT_SECONDS] [--output {text,json,yaml}] [--json] [--dry-run] [--yes] [--subject SUBJECT] --mode {BACKWARD,BACKWARD_TRANSITIVE,FORWARD,FORWARD_TRANSITIVE,FULL,FULL_TRANSITIVE,NONE}

опции:
  -h, --help            показать эту справку и выйти
  --env ENV             Target env: dev|stage|prod
  --cluster CLUSTER     Cluster group. Defaults to default_cluster from
                        connectctl.yaml
  --url URL             Override Schema Registry URL(s), comma-separated
  --timeout-seconds TIMEOUT_SECONDS
                        Schema Registry request timeout, по умолчанию: config value
                        or 10
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
  --dry-run             Build the mutation plan without changing Schema
                        Registry
  --yes, -y             Confirm the live Schema Registry mutation
  --subject SUBJECT     Optional subject
  --mode {BACKWARD,BACKWARD_TRANSITIVE,FORWARD,FORWARD_TRANSITIVE,FULL,FULL_TRANSITIVE,NONE}
                        Desired compatibility mode
```

#### `bkkt schema impact --help`

```text
использование: bkkt schema impact [-h] --env ENV [--cluster CLUSTER] [--url URL] [--timeout-seconds TIMEOUT_SECONDS] [--output {text,json,yaml}] [--json] subject

позиционные аргументы:
  subject               Schema Registry subject

опции:
  -h, --help            показать эту справку и выйти
  --env ENV             Target env: dev|stage|prod
  --cluster CLUSTER     Cluster group. Defaults to default_cluster from
                        connectctl.yaml
  --url URL             Override Schema Registry URL(s), comma-separated
  --timeout-seconds TIMEOUT_SECONDS
                        Schema Registry request timeout, по умолчанию: config value
                        or 10
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
```

#### `bkkt schema plan --help`

```text
использование: bkkt schema plan [-h] --env ENV [--cluster CLUSTER] [--url URL] [--timeout-seconds TIMEOUT_SECONDS] [--output {text,json,yaml}] [--json] --schema-file SCHEMA_FILE --schema-type {AVRO,PROTOBUF,JSON} [--version VERSION] subject

позиционные аргументы:
  subject               Schema Registry subject

опции:
  -h, --help            показать эту справку и выйти
  --env ENV             Target env: dev|stage|prod
  --cluster CLUSTER     Cluster group. Defaults to default_cluster from
                        connectctl.yaml
  --url URL             Override Schema Registry URL(s), comma-separated
  --timeout-seconds TIMEOUT_SECONDS
                        Schema Registry request timeout, по умолчанию: config value
                        or 10
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
  --schema-file SCHEMA_FILE
                        Candidate schema file
  --schema-type {AVRO,PROTOBUF,JSON}
                        Candidate schema type
  --version VERSION     Compatibility version used for preflight, по умолчанию:
                        latest
```

#### `bkkt schema preflight --help`

```text
использование: bkkt schema preflight [-h] --manifest-file MANIFEST_FILE --existing-config-file EXISTING_CONFIG_FILE [--candidate-schema SUBJECT=PATH] [--output {text,json,yaml}] [--json]

опции:
  -h, --help            показать эту справку и выйти
  --manifest-file MANIFEST_FILE
                        Rendered connector manifest JSON/YAML with name,
                        config and optional type metadata.
  --existing-config-file EXISTING_CONFIG_FILE
                        Existing live connector config JSON/YAML.
  --candidate-schema SUBJECT=PATH
                        Optional exact candidate schema file. Can be repeated.
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
```

#### `bkkt schema register --help`

```text
использование: bkkt schema register [-h] --env ENV [--cluster CLUSTER] [--url URL] [--timeout-seconds TIMEOUT_SECONDS] [--output {text,json,yaml}] [--json] [--dry-run] [--yes] --schema-file SCHEMA_FILE --schema-type {AVRO,PROTOBUF,JSON} [--version VERSION] subject

позиционные аргументы:
  subject               Schema Registry subject

опции:
  -h, --help            показать эту справку и выйти
  --env ENV             Target env: dev|stage|prod
  --cluster CLUSTER     Cluster group. Defaults to default_cluster from
                        connectctl.yaml
  --url URL             Override Schema Registry URL(s), comma-separated
  --timeout-seconds TIMEOUT_SECONDS
                        Schema Registry request timeout, по умолчанию: config value
                        or 10
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
  --dry-run             Build the mutation plan without changing Schema
                        Registry
  --yes, -y             Confirm the live Schema Registry mutation
  --schema-file SCHEMA_FILE
                        Schema file to register
  --schema-type {AVRO,PROTOBUF,JSON}
                        Schema type
  --version VERSION     Compatibility version used for preflight, по умолчанию:
                        latest
```

### `bkkt connect --help`

```text
использование: bkkt connect [-h] {status,endpoints,workers,plugins,runtime,offsets,restart,pause,resume,stop,delete,create,update,patch} ...

позиционные аргументы:
  {status,endpoints,workers,plugins,runtime,offsets,restart,pause,resume,stop,delete,create,update,patch}
    status              Показать статус коннекторов
    endpoints           Проверить Kafka Connect REST endpoints внутри cluster
                        group
    workers             Kafka Connect worker inventory
    plugins             Kafka Connect plugin inventory
    runtime             Kafka Connect runtime diagnostics
    offsets             Read/patch Kafka Connect framework-managed connector
                        offsets
    restart             Перезапуск коннекторов
    pause               Пауза коннекторов
    resume              Resume (возобновить) коннекторы
    stop                Stop коннекторы (если поддерживается /stop)
    delete              Удаление коннекторов
    create              Создание коннектора из сырого JSON
    update              Обновление коннектора из сырого JSON
    patch               Patch (частичное обновление) конфига коннектора:
                        GET+merge+PUT

опции:
  -h, --help            показать эту справку и выйти
```

#### `bkkt connect status --help`

```text
использование: bkkt connect status [-h] --env ENV [--cluster CLUSTER] [--names NAMES] [--regexp REGEXP] [--all] [--output {text,json,yaml}] [--json] [--status {short,long,stats}] [--raw-json] [--watch] [--interval-seconds INTERVAL_SECONDS] [--until-healthy] [--timeout-seconds TIMEOUT_SECONDS]

опции:
  -h, --help            показать эту справку и выйти
  --env ENV             Целевое окружение (dev|stage|prod)
  --cluster CLUSTER     Имя группы кластеров (cluster group), либо all/* для
                        fan-out. По умолчанию: default_cluster из
                        connectctl.yaml
  --names NAMES         Имена коннекторов через запятую
  --regexp REGEXP       Регулярное выражение для фильтрации имён (можно
                        указывать несколько раз)
  --all                 Использовать все коннекторы (по умолчанию, если не
                        указаны --names/--regexp)
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
  --status {short,long,stats}
                        short=одна строка на коннектор, long=подробно
                        (tasks/trace), stats=агрегация по состояниям
  --raw-json            (опционально) В режиме --status long дополнительно
                        печатать raw JSON статуса (как вернул Kafka Connect)
  --watch               Обновлять статус в цикле
  --interval-seconds INTERVAL_SECONDS
                        Интервал обновления для --watch (в секундах)
  --until-healthy       Ждать, пока все выбранные коннекторы станут healthy
                        (RUNNING)
  --timeout-seconds TIMEOUT_SECONDS
                        Таймаут ожидания healthy для --until-healthy (в
                        секундах)
```

#### `bkkt connect endpoints --help`

```text
использование: bkkt connect endpoints [-h] --env ENV [--cluster CLUSTER] [--output {text,json,yaml}] [--json] [--name NAME]

опции:
  -h, --help            показать эту справку и выйти
  --env ENV             Целевое окружение (dev|stage|prod)
  --cluster CLUSTER     Имя группы кластеров (cluster group), либо all/* для
                        fan-out. По умолчанию: default_cluster из
                        connectctl.yaml
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
  --name NAME           Дополнительно проверить /status и /config конкретного
                        коннектора
```

#### `bkkt connect workers --help`

```text
использование: bkkt connect workers [-h] {inventory} ...

позиционные аргументы:
  {inventory}
    inventory  List Kafka Connect workers/endpoints and runtime metadata

опции:
  -h, --help   показать эту справку и выйти
```

##### `bkkt connect workers inventory --help`

```text
использование: bkkt connect workers inventory [-h] --env ENV [--cluster CLUSTER] [--output {text,json,yaml}] [--json]

опции:
  -h, --help            показать эту справку и выйти
  --env ENV             Целевое окружение (dev|stage|prod)
  --cluster CLUSTER     Имя группы кластеров (cluster group), либо all/* для
                        fan-out. По умолчанию: default_cluster из
                        connectctl.yaml
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
```

#### `bkkt connect plugins --help`

```text
использование: bkkt connect plugins [-h] {inventory} ...

позиционные аргументы:
  {inventory}
    inventory  List Kafka Connect connector plugins and versions

опции:
  -h, --help   показать эту справку и выйти
```

##### `bkkt connect plugins inventory --help`

```text
использование: bkkt connect plugins inventory [-h] --env ENV [--cluster CLUSTER] [--output {text,json,yaml}] [--json]

опции:
  -h, --help            показать эту справку и выйти
  --env ENV             Целевое окружение (dev|stage|prod)
  --cluster CLUSTER     Имя группы кластеров (cluster group), либо all/* для
                        fan-out. По умолчанию: default_cluster из
                        connectctl.yaml
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
```

#### `bkkt connect runtime --help`

```text
использование: bkkt connect runtime [-h] {diff} ...

позиционные аргументы:
  {diff}
    diff      Compare configured runtime metadata with REST diagnostics

опции:
  -h, --help  показать эту справку и выйти
```

##### `bkkt connect runtime diff --help`

```text
использование: bkkt connect runtime diff [-h] --env ENV [--cluster CLUSTER] [--output {text,json,yaml}] [--json]

опции:
  -h, --help            показать эту справку и выйти
  --env ENV             Целевое окружение (dev|stage|prod)
  --cluster CLUSTER     Имя группы кластеров (cluster group), либо all/* для
                        fan-out. По умолчанию: default_cluster из
                        connectctl.yaml
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
```

#### `bkkt connect offsets --help`

```text
использование: bkkt connect offsets [-h] {get,patch} ...

позиционные аргументы:
  {get,patch}
    get        Read connector offsets
    patch      Patch connector offsets

опции:
  -h, --help   показать эту справку и выйти
```

##### `bkkt connect offsets get --help`

```text
использование: bkkt connect offsets get [-h] --env ENV [--cluster CLUSTER] [--output {text,json,yaml}] [--json] --name NAME

опции:
  -h, --help            показать эту справку и выйти
  --env ENV             Целевое окружение (dev|stage|prod)
  --cluster CLUSTER     Имя группы кластеров (cluster group), либо all/* для
                        fan-out. По умолчанию: default_cluster из
                        connectctl.yaml
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: json
  --json                Alias для --output json (устаревает, используйте
                        --output json)
  --name NAME           Connector name
```

##### `bkkt connect offsets patch --help`

```text
использование: bkkt connect offsets patch [-h] --env ENV [--cluster CLUSTER] --name NAME --json-file JSON_FILE [--dry-run] [--runtime-unsafe-rest] [-y]

опции:
  -h, --help            показать эту справку и выйти
  --env ENV             Целевое окружение (dev|stage|prod)
  --cluster CLUSTER     Имя группы кластеров (cluster group), либо all/* для
                        fan-out. По умолчанию: default_cluster из
                        connectctl.yaml
  --name NAME           Connector name
  --json-file JSON_FILE
                        Path to Kafka Connect offsets PATCH JSON payload
  --dry-run             Show plan without PATCH
  --runtime-unsafe-rest
                        Break-glass: allow raw Kafka Connect REST mutations
                        for operator-managed runtimes (Strimzi/CFK). Prefer
                        CRD/GitOps mutation instead.
  -y, --yes             Required confirmation for live offsets PATCH
```

#### `bkkt connect restart --help`

```text
использование: bkkt connect restart [-h] --env ENV [--cluster CLUSTER] [--clusters [CLUSTERS]] [--names NAMES] [--regexp REGEXP] [--all] [--jobs JOBS] [--rate-limit-per-second RATE_LIMIT_PER_SECOND] [--runtime-unsafe-rest] [--output {text,json,yaml}] [--json] [-y] [--scope {failed,failed-tasks,all}] [--dry-run]

опции:
  -h, --help            показать эту справку и выйти
  --env ENV             Целевое окружение (dev|stage|prod)
  --cluster CLUSTER     Имя группы кластеров (cluster group), либо all/* для
                        fan-out. По умолчанию: default_cluster из
                        connectctl.yaml
  --clusters [CLUSTERS]
                        Bulk recovery по набору cluster groups без override.
                        Укажите список через запятую или используйте
                        --clusters all. Нельзя использовать вместе с
                        --cluster.
  --names NAMES         Имена коннекторов через запятую
  --regexp REGEXP       Регулярное выражение для фильтрации имён (можно
                        указывать несколько раз)
  --all                 Использовать все коннекторы (обязательно, если не
                        указаны --names/--regexp)
  --jobs JOBS           Параллелизм (кол-во потоков) для массовых операций. По
                        умолчанию: 1 (последовательно)
  --rate-limit-per-second RATE_LIMIT_PER_SECOND
                        Ограничение REST запросов в секунду (RPS) ко всем
                        Connect URL вместе. Если не задано и --jobs > 1,
                        включается безопасный лимит (по умолчанию ~5 RPS). 0 =
                        выключить ограничение.
  --runtime-unsafe-rest
                        Break-glass: allow raw Kafka Connect REST mutations
                        for operator-managed runtimes (Strimzi/CFK). Prefer
                        CRD/GitOps mutation instead.
  --output {text,json,yaml}
                        Формат вывода результата в stdout (text|json|yaml). По
                        умолчанию: text
  --json                Alias для --output json (устаревает, используйте
                        --output json)
  -y, --yes             Не спрашивать подтверждение для широкого restart
                        recovery
  --scope {failed,failed-tasks,all}
                        failed=только FAILED connector, failed-tasks=FAILED
                        connector или tasks, all=все
  --dry-run             Ничего не делать, только показать план
```

#### `bkkt connect pause --help`

```text
использование: bkkt connect pause [-h] --env ENV [--cluster CLUSTER] [--names NAMES] [--regexp REGEXP] [--all] [--jobs JOBS] [--rate-limit-per-second RATE_LIMIT_PER_SECOND] [--runtime-unsafe-rest] [-y] [--dry-run]

опции:
  -h, --help            показать эту справку и выйти
  --env ENV             Целевое окружение (dev|stage|prod)
  --cluster CLUSTER     Имя группы кластеров (cluster group), либо all/* для
                        fan-out. По умолчанию: default_cluster из
                        connectctl.yaml
  --names NAMES         Имена коннекторов через запятую
  --regexp REGEXP       Регулярное выражение для фильтрации имён (можно
                        указывать несколько раз)
  --all                 Использовать все коннекторы (обязательно, если не
                        указаны --names/--regexp)
  --jobs JOBS           Параллелизм (кол-во потоков) для массовых операций. По
                        умолчанию: 1 (последовательно)
  --rate-limit-per-second RATE_LIMIT_PER_SECOND
                        Ограничение REST запросов в секунду (RPS) ко всем
                        Connect URL вместе. Если не задано и --jobs > 1,
                        включается безопасный лимит (по умолчанию ~5 RPS). 0 =
                        выключить ограничение.
  --runtime-unsafe-rest
                        Break-glass: allow raw Kafka Connect REST mutations
                        for operator-managed runtimes (Strimzi/CFK). Prefer
                        CRD/GitOps mutation instead.
  -y, --yes             Не спрашивать подтверждение для mutating операций
  --dry-run             Ничего не делать, только показать план
```

#### `bkkt connect resume --help`

```text
использование: bkkt connect resume [-h] --env ENV [--cluster CLUSTER] [--names NAMES] [--regexp REGEXP] [--all] [--jobs JOBS] [--rate-limit-per-second RATE_LIMIT_PER_SECOND] [--runtime-unsafe-rest] [-y] [--dry-run]

опции:
  -h, --help            показать эту справку и выйти
  --env ENV             Целевое окружение (dev|stage|prod)
  --cluster CLUSTER     Имя группы кластеров (cluster group), либо all/* для
                        fan-out. По умолчанию: default_cluster из
                        connectctl.yaml
  --names NAMES         Имена коннекторов через запятую
  --regexp REGEXP       Регулярное выражение для фильтрации имён (можно
                        указывать несколько раз)
  --all                 Использовать все коннекторы (обязательно, если не
                        указаны --names/--regexp)
  --jobs JOBS           Параллелизм (кол-во потоков) для массовых операций. По
                        умолчанию: 1 (последовательно)
  --rate-limit-per-second RATE_LIMIT_PER_SECOND
                        Ограничение REST запросов в секунду (RPS) ко всем
                        Connect URL вместе. Если не задано и --jobs > 1,
                        включается безопасный лимит (по умолчанию ~5 RPS). 0 =
                        выключить ограничение.
  --runtime-unsafe-rest
                        Break-glass: allow raw Kafka Connect REST mutations
                        for operator-managed runtimes (Strimzi/CFK). Prefer
                        CRD/GitOps mutation instead.
  -y, --yes             Не спрашивать подтверждение для mutating операций
  --dry-run             Ничего не делать, только показать план
```

#### `bkkt connect stop --help`

```text
использование: bkkt connect stop [-h] --env ENV [--cluster CLUSTER] [--names NAMES] [--regexp REGEXP] [--all] [--jobs JOBS] [--rate-limit-per-second RATE_LIMIT_PER_SECOND] [--runtime-unsafe-rest] [-y] [--dry-run]

опции:
  -h, --help            показать эту справку и выйти
  --env ENV             Целевое окружение (dev|stage|prod)
  --cluster CLUSTER     Имя группы кластеров (cluster group), либо all/* для
                        fan-out. По умолчанию: default_cluster из
                        connectctl.yaml
  --names NAMES         Имена коннекторов через запятую
  --regexp REGEXP       Регулярное выражение для фильтрации имён (можно
                        указывать несколько раз)
  --all                 Использовать все коннекторы (обязательно, если не
                        указаны --names/--regexp)
  --jobs JOBS           Параллелизм (кол-во потоков) для массовых операций. По
                        умолчанию: 1 (последовательно)
  --rate-limit-per-second RATE_LIMIT_PER_SECOND
                        Ограничение REST запросов в секунду (RPS) ко всем
                        Connect URL вместе. Если не задано и --jobs > 1,
                        включается безопасный лимит (по умолчанию ~5 RPS). 0 =
                        выключить ограничение.
  --runtime-unsafe-rest
                        Break-glass: allow raw Kafka Connect REST mutations
                        for operator-managed runtimes (Strimzi/CFK). Prefer
                        CRD/GitOps mutation instead.
  -y, --yes             Не спрашивать подтверждение для mutating операций
  --dry-run             Ничего не делать, только показать план
```

#### `bkkt connect delete --help`

```text
использование: bkkt connect delete [-h] --env ENV [--cluster CLUSTER] [--names NAMES] [--regexp REGEXP] [--all] [--jobs JOBS] [--rate-limit-per-second RATE_LIMIT_PER_SECOND] [--runtime-unsafe-rest] [-y] [--unsafe] [--dry-run]

опции:
  -h, --help            показать эту справку и выйти
  --env ENV             Целевое окружение (dev|stage|prod)
  --cluster CLUSTER     Имя группы кластеров (cluster group), либо all/* для
                        fan-out. По умолчанию: default_cluster из
                        connectctl.yaml
  --names NAMES         Имена коннекторов через запятую
  --regexp REGEXP       Регулярное выражение для фильтрации имён (можно
                        указывать несколько раз)
  --all                 Использовать все коннекторы (обязательно, если не
                        указаны --names/--regexp)
  --jobs JOBS           Параллелизм (кол-во потоков) для массовых операций. По
                        умолчанию: 1 (последовательно)
  --rate-limit-per-second RATE_LIMIT_PER_SECOND
                        Ограничение REST запросов в секунду (RPS) ко всем
                        Connect URL вместе. Если не задано и --jobs > 1,
                        включается безопасный лимит (по умолчанию ~5 RPS). 0 =
                        выключить ограничение.
  --runtime-unsafe-rest
                        Break-glass: allow raw Kafka Connect REST mutations
                        for operator-managed runtimes (Strimzi/CFK). Prefer
                        CRD/GitOps mutation instead.
  -y, --yes             Не спрашивать подтверждение
  --unsafe              Отключить safe pre-delete checks и сразу отправить
                        DELETE. По умолчанию delete работает в safe mode.
  --dry-run             Ничего не делать, только показать план
```

#### `bkkt connect create --help`

```text
использование: bkkt connect create [-h] --env ENV [--cluster CLUSTER] [--runtime-unsafe-rest] [--name NAME] [--dry-run] [--failure-bundle-dir FAILURE_BUNDLE_DIR] [src]

позиционные аргументы:
  src                   JSON файл или '-' для stdin (по умолчанию: -)

опции:
  -h, --help            показать эту справку и выйти
  --env ENV             Целевое окружение (dev|stage|prod)
  --cluster CLUSTER     Имя группы кластеров (cluster group), либо all/* для
                        fan-out. По умолчанию: default_cluster из
                        connectctl.yaml
  --runtime-unsafe-rest
                        Break-glass: allow raw Kafka Connect REST mutations
                        for operator-managed runtimes (Strimzi/CFK). Prefer
                        CRD/GitOps mutation instead.
  --name NAME           Имя коннектора (если payload не содержит 'name')
  --dry-run             Ничего не делать, только показать план
  --failure-bundle-dir FAILURE_BUNDLE_DIR
                        Каталог для diagnostic failure bundles. При ошибке
                        BKKT сохранит prepared manifest, routing и error
                        payload в отдельный подкаталог (по умолчанию:
                        artifacts/failure-bundles/connect-create).
```

#### `bkkt connect update --help`

```text
использование: bkkt connect update [-h] --env ENV [--cluster CLUSTER] [--runtime-unsafe-rest] [--name NAME] [--dry-run] [--diff] [--diff-max-keys DIFF_MAX_KEYS] [--skip-if-no-change | --no-skip-if-no-change] [--failure-bundle-dir FAILURE_BUNDLE_DIR] [src]

позиционные аргументы:
  src                   JSON файл или '-' для stdin (по умолчанию: -)

опции:
  -h, --help            показать эту справку и выйти
  --env ENV             Целевое окружение (dev|stage|prod)
  --cluster CLUSTER     Имя группы кластеров (cluster group), либо all/* для
                        fan-out. По умолчанию: default_cluster из
                        connectctl.yaml
  --runtime-unsafe-rest
                        Break-glass: allow raw Kafka Connect REST mutations
                        for operator-managed runtimes (Strimzi/CFK). Prefer
                        CRD/GitOps mutation instead.
  --name NAME           Имя коннектора (если payload не содержит 'name')
  --dry-run             Ничего не делать, только показать план
  --diff                В --dry-run показать структурный diff
                        (removed/added/changed keys)
  --diff-max-keys DIFF_MAX_KEYS
                        Лимит ключей на секцию для --diff (по умолчанию: 50)
  --skip-if-no-change, --no-skip-if-no-change
                        Пропускать PUT, если конфиг не меняется (по умолчанию:
                        да)
  --failure-bundle-dir FAILURE_BUNDLE_DIR
                        Каталог для diagnostic failure bundles. При ошибке
                        BKKT сохранит prepared manifest, routing и error
                        payload в отдельный подкаталог (по умолчанию:
                        artifacts/failure-bundles/connect-update).
```

#### `bkkt connect patch --help`

```text
использование: bkkt connect patch [-h] --env ENV [--cluster CLUSTER] [--state-db STATE_DB] [--no-audit] [--names NAMES] [--regexp REGEXP] [--all] [--jobs JOBS] [--rate-limit-per-second RATE_LIMIT_PER_SECOND] [--runtime-unsafe-rest] [--json JSON] [--json-file JSON_FILE] [--set SET] [--set-csv SET_CSV] [--set-file SET_FILE] [--stdin] [--dry-run] [-y] [--diff] [--diff-max-keys DIFF_MAX_KEYS] [--skip-if-no-change | --no-skip-if-no-change] [--failure-bundle-dir FAILURE_BUNDLE_DIR]

опции:
  -h, --help            показать эту справку и выйти
  --env ENV             Целевое окружение (dev|stage|prod)
  --cluster CLUSTER     Имя группы кластеров (cluster group), либо all/* для
                        fan-out. По умолчанию: default_cluster из
                        connectctl.yaml
  --state-db STATE_DB   Path to BKKT SQLite state DB. Defaults to
                        .bkkt/state/bkkt.sqlite or BKKT_STATE_DB.
  --no-audit            Disable local SQLite audit write for this command.
  --names NAMES         Имена коннекторов через запятую
  --regexp REGEXP       Регулярное выражение для фильтрации имён (можно
                        указывать несколько раз)
  --all                 Использовать все коннекторы (обязательно, если не
                        указаны --names/--regexp)
  --jobs JOBS           Параллелизм (кол-во потоков) для массовых операций. По
                        умолчанию: 1 (последовательно)
  --rate-limit-per-second RATE_LIMIT_PER_SECOND
                        Ограничение REST запросов в секунду (RPS) ко всем
                        Connect URL вместе. Если не задано и --jobs > 1,
                        включается безопасный лимит (по умолчанию ~5 RPS). 0 =
                        выключить ограничение.
  --runtime-unsafe-rest
                        Break-glass: allow raw Kafka Connect REST mutations
                        for operator-managed runtimes (Strimzi/CFK). Prefer
                        CRD/GitOps mutation instead.
  --json JSON           JSON patch объект inline. Можно несколько раз;
                        последние значения побеждают. JSON null = удалить
                        ключ.
  --json-file JSON_FILE
                        Путь к JSON файлу с patch объектом. Можно несколько
                        раз. JSON null = удалить ключ.
  --set SET             Literal key=value запись. Можно несколько раз. Запятые
                        внутри value сохраняются. value __DELETE__ = удалить
                        ключ.
  --set-csv SET_CSV     Legacy CSV key=value записи через запятую: k=v,k2=v2.
                        Для table.include.list используйте обычный --set.
  --set-file SET_FILE   Файл с key=value (по строкам или CSV). Можно несколько
                        раз. value __DELETE__ = удалить ключ.
  --stdin               Также прочитать patch из stdin (JSON или key=value).
                        Применяется последним.
  --dry-run             Ничего не делать, только показать план
  -y, --yes             Разрешить реальный fan-out patch для --cluster all.
                        Для single-cluster patch поведение не меняет.
  --diff                В --dry-run показать структурный diff
                        (removed/added/changed keys) вместо unified diff
  --diff-max-keys DIFF_MAX_KEYS
                        Лимит ключей на секцию для --diff (по умолчанию: 50)
  --skip-if-no-change, --no-skip-if-no-change
                        Пропускать PUT, если итоговый конфиг не меняется (по
                        умолчанию: да)
  --failure-bundle-dir FAILURE_BUNDLE_DIR
                        Каталог для diagnostic failure bundles. При ошибке
                        BKKT сохранит prepared manifest, routing и error
                        payload в отдельный подкаталог (по умолчанию:
                        artifacts/failure-bundles/connect-patch).
```

### `bkkt sync --help`

```text
использование: bkkt sync [-h] --env ENV [--cluster CLUSTER] [--clusters [CLUSTERS]] [--suppress-tag-conflicts] [--prune] [--allow-regex ALLOW_REGEX] [--deny-regex DENY_REGEX] [--allow-name ALLOW_NAME] [--deny-name DENY_NAME] [--keep-regex KEEP_REGEX] [--dry-run] [--connect-validate] [--no-connect-validate] [--rollback-on-fail] [--no-rollback-on-fail] [--wait-seconds WAIT_SECONDS] [--timeout-seconds TIMEOUT_SECONDS] [--poll-interval-seconds POLL_INTERVAL_SECONDS] [--vars VARS] [--vars-file VARS_FILE] [--vars-profile VARS_PROFILE] [--no-strict-naming] [--no-policies] [--no-skip-if-unchanged] [--force] [-y] [--drop-if-exists] [--drop-if-failed] [--no-auto-catalog] [--no-smoke] [--smoke-strict]

опции:
  -h, --help            показать эту справку и выйти
  --env ENV             Целевое окружение (dev|stage|prod)
  --cluster CLUSTER     Имя группы кластеров (cluster group). Если задано —
                        принудительно использовать этот кластер для всех
                        коннекторов (override). Если не задано — sync работает
                        в multi-cluster режиме и группирует коннекторы по
                        routing (connectctl.cluster/tags/default_cluster),
                        синхронизируя каждый кластер отдельно. Если вы хотите
                        синхронизировать только один кластер, НЕ перекидывая
                        все коннекторы override-ом, используйте --clusters
                        (filter-by-cluster).
  --clusters [CLUSTERS]
                        Фильтр sync по набору cluster groups (без override).
                        Роутинг сохраняется: синхронизируются только
                        'естественные' коннекторы выбранных кластеров. Укажите
                        список через запятую (например: main,source). Если
                        указать без значения, включаются ВСЕ cluster groups из
                        connectctl.yaml. Нельзя использовать вместе с
                        --cluster (override).
  --suppress-tag-conflicts
                        Если несколько тегов задают один и тот же параметр
                        разными значениями: вывести warning и взять значение
                        последнего тега. Параметры из
                        tags.hard_conflict_params всегда приводят к ошибке.
  --prune               Удалить коннекторы, которые есть в Connect, но
                        отсутствуют в repo
  --allow-regex ALLOW_REGEX
                        Allow-list regex для имён коннекторов, которые можно
                        prune (можно повторять)
  --deny-regex DENY_REGEX
                        Deny-list regex для имён коннекторов, которые нельзя
                        prune (можно повторять)
  --allow-name ALLOW_NAME
                        Явный allow-list имён коннекторов для prune (можно
                        повторять)
  --deny-name DENY_NAME
                        Явный deny-list имён коннекторов для prune (можно
                        повторять)
  --keep-regex KEEP_REGEX
                        (Deprecated) alias of --deny-regex. Regex имён
                        коннекторов, которые надо сохранить при prune
  --dry-run             Ничего не применять в Kafka Connect (только показать
                        план)
  --connect-validate    Валидировать конфиг через plugin validate endpoint
                        перед upsert (по умолчанию: включено)
  --no-connect-validate
                        Отключить validate через Kafka Connect (НЕ
                        рекомендуется)
  --rollback-on-fail    Rollback к предыдущей конфигурации при ошибке apply
                        (по умолчанию: включено на stage/prod)
  --no-rollback-on-fail
                        Отключить rollback при ошибке
  --wait-seconds WAIT_SECONDS
                        Пауза после apply перед началом polling
  --timeout-seconds TIMEOUT_SECONDS
                        Общий timeout ожидания статуса
  --poll-interval-seconds POLL_INTERVAL_SECONDS
                        Интервал polling статуса
  --vars VARS           dbt-style vars JSON (object). Можно повторять;
                        мерджится, побеждает последнее значение.
  --vars-file VARS_FILE
                        Путь к JSON/YAML файлу vars (object). Можно повторять;
                        мерджится. Перебивается --vars.
  --vars-profile VARS_PROFILE
                        Имя профиля из bkkt/vars/profiles/*.yaml. Можно
                        повторять.
  --no-strict-naming    Отключить строгую валидацию нейминга (НЕ
                        рекомендуется). Проверяет dot-style имена и базовые
                        инварианты: env в начале, domain во 2-м сегменте,
                        наличие 'source'/'sink' и system, последний сегмент —
                        числовой индекс, а также (если настроено) правила
                        connectctl.yaml:naming.rules. Подробнее:
                        docs/NAMING.md (или `bkkt help naming`).
  --no-policies         Отключить policy‑проверки окружения (НЕ
                        рекомендуется). Эти проверки ловят потенциально
                        опасные ссылки на чужое окружение (dev/stage/prod) и
                        другие ошибки. Подробнее: docs/POLICIES.md (или `bkkt
                        help policies`).
  --no-skip-if-unchanged
                        Отключить drift-skip и всегда делать upsert
  --force               Force upsert даже если конфиг не изменился
  -y, --yes             Не спрашивать подтверждение для широкого multi-cluster
                        sync
  --drop-if-exists      Удалять коннектор перед apply, если он уже существует
                        (ОПАСНО)
  --drop-if-failed      Если деплой упал и коннектор остался FAILED — удалить
                        его (по умолчанию: выключено)
  --no-auto-catalog     Отключить авто-создание AWS Glue databases для Iceberg
                        sinks
  --no-smoke            Отключить Kafka smoke checks (topics existence / sink
                        lag)
  --smoke-strict        Падать с ошибкой, если smoke checks нашли проблемы
```

### `bkkt init --help`

```text
использование: bkkt init [-h] --domain DOMAIN --type {source,sink} --system SYSTEM [--connector-dir CONNECTOR_DIR] --env {dev,stage,prod} [--modes MODES] [--init-only] [--kinds KINDS] [--dataset DATASET] [--layer LAYER] [--index INDEX] [--name NAME] [--name-template NAME_TEMPLATE] [--create-all] [--no-create-all] [--force] [--dry-run] [--tpl-json TPL_JSON] [--tpl-json-file TPL_JSON_FILE] [--tpl-json-scoped TPL_JSON_SCOPED] [--tpl-json-file-scoped TPL_JSON_FILE_SCOPED] [--tpl-set TPL_SET] [--tpl-set-file TPL_SET_FILE] [--tpl-set-scoped TPL_SET_SCOPED] [--tpl-set-file-scoped TPL_SET_FILE_SCOPED] [--tpl-stdin]

опции:
  -h, --help            показать эту справку и выйти
  --domain DOMAIN       Домен (папка верхнего уровня), напр. merchants
  --type {source,sink}  Тип коннектора
  --system SYSTEM       Система (папка), напр.
                        postgres/mysql/iceberg/clickhouse/mariadb
  --connector-dir CONNECTOR_DIR
                        Имя директории коннектора. Необязательный параметр. По
                        умолчанию: connector_<domain>__<dataset>. Должно
                        соответствовать шаблону:
                        connector_<domain>__<dataset>{__<optional_suffix>}
  --env {dev,stage,prod}
                        Окружение(я); можно указывать несколько раз
  --modes MODES         Только для source. Список (CSV или повторяемый)
                        режимов (modes) для генерации. Встроенные: cdc, init
                        (алиасы: stream->cdc, initial->init). Также можно
                        указывать свои modes (например backfill/replay) — init
                        создаст modes/<mode>/* и вставит токен в имя
                        (.backfill.). Пример: --modes init,cdc
  --init-only           Только для source. Удобный флаг: создаёт
                        <connector_dir>/modes/init/all.json с
                        vars.debezium_snapshot_mode_init=initial_only (чтобы
                        init был init-only из коробки). Если --modes указан,
                        но init/initial отсутствуют — init будет добавлен
                        автоматически.
  --kinds KINDS         Только для sink. Список (CSV или повторяемый) sink
                        kinds (variants) для генерации. Для CDC sink kind
                        попадает в имя как '.cdc.<kind>.' и включает overlays
                        'types/<kind>/*'. Если --kinds не задан, генерируется
                        простой sink без '.cdc' (kind будет выведен из
                        --layer: raw/ods, либо 'default'). Пример: --kinds
                        events,flatten
  --dataset DATASET     Dataset (используется в шаблонах и connector_dir)
  --layer LAYER         Только для sink. Логический слой (обычно raw или ods):
                        попадает в имя после `.sink.` и в vars.layer. Для non-
                        CDC sink (без `.cdc`) также влияет на kind (types/raw
                        vs types/ods).
  --index INDEX         Index для дефолтного шаблона имени
  --name NAME           Явное имя коннектора (или format string)
  --name-template NAME_TEMPLATE
                        Python format string для имени. Доступные переменные:
                        env, domain, dataset, type, system, layer, index,
                        connector_dir, mode, kind. Пример: '{env}.{domain}.{da
                        taset}.source.{system}.{mode}.dbt.{index}'
  --create-all          Создать all.json в директории коннектора
  --no-create-all       Не создавать all.json
  --force               Перезаписывать существующие файлы
  --dry-run             Показать действия без записи файлов
  --tpl-json TPL_JSON   JSON overrides для init-templates (vars/config). Можно
                        несколько раз. Поддерживается scoped формат:
                        <scope>:<json>. Scope — glob относительно
                        connector_dir (например: 'modes/init/*',
                        'types/events/*'). Порядок приоритетов (low->high):
                        built-in < __init_templates/ (или
                        BKKT_INIT_TEMPLATES_ROOT) <
                        BKKT_INIT_TPL/BKKT_INIT_TPL_FILE < --tpl-* < --tpl-
                        stdin. Поздние значения имеют более высокий приоритет.
                        Если JSON не содержит ключей vars/config — он
                        трактуется как набор config-ключей.
  --tpl-json-file TPL_JSON_FILE
                        Файл с JSON overrides для init-templates. Можно
                        несколько раз. Поддерживается scoped формат:
                        <scope>:<path>.
  --tpl-json-scoped TPL_JSON_SCOPED
                        [LEGACY] Scoped JSON overrides для init-templates.
                        Формат: <scope>:<json>. Рекомендуется использовать
                        --tpl-json '<scope>:<json>' без отдельного флага.
                        Scope — glob относительно connector_dir (например:
                        'modes/init/*' или 'types/events/*'). Можно несколько
                        раз; поздние значения имеют более высокий приоритет.
  --tpl-json-file-scoped TPL_JSON_FILE_SCOPED
                        [LEGACY] Файл со scoped JSON overrides. Формат:
                        <scope>:<path>. Рекомендуется использовать --tpl-json-
                        file '<scope>:<path>' без отдельного флага. Пример:
                        'modes/init/*:overrides.json'. Можно несколько раз.
  --tpl-set TPL_SET     key=value overrides для init-templates (CSV). Можно
                        несколько раз. Поддерживается scoped формат:
                        <scope>:k=v[,k=v]. Scope — glob относительно
                        connector_dir (например: 'modes/init/*',
                        'types/events/*'). Поддерживается префикс vars.<path>
                        и config.<key>. Если префикса нет — ключ пытается
                        матчиться в vars, иначе считается config-ключом.
  --tpl-set-file TPL_SET_FILE
                        Файл с key=value overrides для init-templates (по
                        строкам или CSV). Можно несколько раз. Поддерживается
                        scoped формат: <scope>:<path>.
  --tpl-set-scoped TPL_SET_SCOPED
                        [LEGACY] Scoped key=value overrides для init-
                        templates. Формат: <scope>:k=v[,k=v]. Рекомендуется
                        использовать --tpl-set '<scope>:k=v' без отдельного
                        флага. Пример:
                        'types/events/*:vars.layer=events,vars.index=1'. Можно
                        несколько раз.
  --tpl-set-file-scoped TPL_SET_FILE_SCOPED
                        [LEGACY] Файл со scoped key=value overrides. Формат:
                        <scope>:<path>. Рекомендуется использовать --tpl-set-
                        file '<scope>:<path>' без отдельного флага. Пример:
                        'modes/init/*:overrides.kv'. Можно несколько раз.
  --tpl-stdin           Также прочитать overrides из stdin (JSON или
                        key=value). Применяется последним.

Подробнее про init templates, modes/kinds и порядок overrides: docs/INIT.md
Шаблоны: built-in → __init_templates/ (или BKKT_INIT_TEMPLATES_ROOT).
Overrides: BKKT_INIT_TPL/BKKT_INIT_TPL_FILE → --tpl-* → --tpl-stdin (последние
побеждают). Scoped overrides: <scope>:..., где scope — glob относительно
connector_dir (например: modes/init/*, types/events/*).
```

### `bkkt validate --help`

```text
использование: bkkt validate [-h] [--env ENV] [--changed] [--strict-naming] [--strict-schema] [--strict-schema-max STRICT_SCHEMA_MAX] [--strict-connector-dir] [--connector-dir-lint-scope {all,changed}] [--connector-dir-lint-max CONNECTOR_DIR_LINT_MAX] [--base BASE] [--head HEAD] [--vars VARS] [--vars-file VARS_FILE] [--vars-profile VARS_PROFILE] [paths ...]

позиционные аргументы:
  paths                 Явные manifest paths для валидации

опции:
  -h, --help            показать эту справку и выйти
  --env ENV             Валидировать только одно окружение (dev|stage|prod)
  --changed             Валидировать только коннекторы, затронутые git diff
  --strict-naming       Включить строгую валидацию нейминга (CI gate).
                        Проверяет dot-style и (если настроено)
                        connectctl.yaml:naming.rules. Подробнее:
                        docs/NAMING.md (или `bkkt help naming`).
  --strict-schema       Строгая JSON Schema валидация: connectctl.yaml и
                        manifest JSON (CI gate)
  --strict-schema-max STRICT_SCHEMA_MAX
                        Сколько schema ошибок показывать в логах (top-N).
                        (по умолчанию: 20)
  --strict-connector-dir
                        Считать repo-wide lint по шаблону connector_dir
                        ошибкой (по умолчанию это warning). Проверка:
                        connector_<domain>__<dataset>{__<optional_suffix>}
  --connector-dir-lint-scope {all,changed}
                        Область repo-wide lint для connector_dir.
                        all=проверять весь репозиторий (по умолчанию).
                        changed=проверять только каталоги, затронутые
                        --changed (или явными путями в конце команды).
  --connector-dir-lint-max CONNECTOR_DIR_LINT_MAX
                        Сколько нарушений connector_dir печатать в логах
                        (top-N). Остальные будут свернуты как '… и ещё X…'.
                        (по умолчанию: 20)
  --base BASE           Base git sha (по умолчанию: auto)
  --head HEAD           Head git sha (по умолчанию: HEAD)
  --vars VARS           dbt-style vars JSON (object). Можно повторять;
                        мерджится, побеждает последнее значение.
  --vars-file VARS_FILE
                        Путь к JSON/YAML файлу vars (object). Можно повторять;
                        мерджится. Перебивается --vars.
  --vars-profile VARS_PROFILE
                        Имя профиля из bkkt/vars/profiles/*.yaml. Можно
                        повторять.
```

### `bkkt validate-connect --help`

```text
использование: bkkt validate-connect [-h] --env ENV [--cluster CLUSTER] [--suppress-tag-conflicts] [--changed] [--all] [--base BASE] [--head HEAD] [--strict-naming] [--max-errors MAX_ERRORS] [--vars VARS] [--vars-file VARS_FILE] [--vars-profile VARS_PROFILE] [paths ...]

позиционные аргументы:
  paths                 Явные manifest paths (если не --changed)

опции:
  -h, --help            показать эту справку и выйти
  --env ENV             Окружение (dev|stage|prod). В bulk-режиме с --all
                        также поддерживается env=all.
  --cluster CLUSTER     Имя cluster group. Без --all: если задано —
                        принудительно валидировать коннекторы в этом кластере.
                        С --all: cluster=all валидирует все выбранные
                        manifests по обычному routing, cluster=<name>
                        фильтрует только manifests, чей normal routing идёт в
                        этот cluster group. Если не задано — кластер
                        выбирается per-connector через routing
                        (connectctl.cluster/tags/default_cluster). Важно:
                        плагины могут отличаться на разных кластерах.
  --suppress-tag-conflicts
                        Если несколько тегов задают один и тот же параметр
                        разными значениями: вывести warning и взять значение
                        последнего тега. Параметры из
                        tags.hard_conflict_params всегда приводят к ошибке.
  --changed             Валидировать только manifests, затронутые git diff
  --all                 Валидировать все deployable wrapper manifests из
                        репозитория
  --base BASE           Base git sha (по умолчанию: auto)
  --head HEAD           Head git sha (по умолчанию: auto)
  --strict-naming       Включить строгую валидацию нейминга (CI gate).
                        Проверяет dot-style и (если настроено)
                        connectctl.yaml:naming.rules. Подробнее:
                        docs/NAMING.md (или `bkkt help naming`). (перед
                        Connect validate)
  --max-errors MAX_ERRORS
                        Максимум per-field validation errors (по умолчанию:
                        20)
  --vars VARS           dbt-style vars JSON (object). Можно повторять;
                        мерджится, побеждает последнее.
  --vars-file VARS_FILE
                        Путь к JSON/YAML vars (object). Можно повторять;
                        мерджится. Перебивается --vars.
  --vars-profile VARS_PROFILE
                        Имя профиля из bkkt/vars/profiles/*.yaml. Можно
                        повторять.
```

<!-- BKKT_CLI_REFERENCE_COMMANDS_END -->
