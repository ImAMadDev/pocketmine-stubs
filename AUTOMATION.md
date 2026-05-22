# 🤖 Automatización: Check New PocketMine-MP Releases

Este workflow automatiza la detección de nuevas versiones de PocketMine-MP y la generación de stubs, creando PRs automáticamente.

## 📅 Scheduled Automation

El workflow se ejecuta **automáticamente cada 6 horas** mediante cron, pero también puede ejecutarse manualmente.

### Trigger: `schedule`

```yaml
schedule:
  - cron: "0 */6 * * *"
```

**¿Cuándo se ejecuta?**
- Cada 6 horas: `0:00, 6:00, 12:00, 18:00 UTC`

---

## 🎯 Flujo de Ejecución

```
┌────────────────────────────────────────────────────────────────┐
│ Cada 6 horas o manual (workflow_dispatch)                     │
└───────────────────────┬────────────────────────────────────────┘
                        │
                        ▼
        ┌───────────────────────────────────┐
        │ Job 1: check-releases             │
        │ ├─ ¿Nueva versión en PMMP?        │
        │ ├─ ¿Ya en manifest.json?          │
        │ └─ Extraer MC version             │
        └───────────────┬───────────────────┘
                        │
                        ▼
            ¿needs_update = true?
                        │
        ┌───────────────┴───────────────┐
        │ NO                            │ SÍ
        ▼                               ▼
    (Stop)                  ┌──────────────────────────┐
                            │ Job 2: generate-stubs    │
                            │ ├─ python generate.py    │
                            │ ├─ SHA256                │
                            │ └─ Verificar ZIP         │
                            └────────┬─────────────────┘
                                     │
                                     ▼
                            ┌──────────────────────────┐
                            │ Job 3: auto-update       │
                            │ ├─ Crear rama            │
                            │ ├─ Commit manifest       │
                            │ ├─ Push                  │
                            │ └─ Crear PR              │
                            └────────┬─────────────────┘
                                     │
                                     ▼
                        ┌────────────────────────────┐
                        │ ✅ PR creado automáticamente│
                        │    Esperando revisión      │
                        └────────────────────────────┘
```

---

## 🔍 Job 1: `check-releases`

**¿Qué hace?**

Detecta nuevas versiones de PocketMine-MP y verifica si ya están en manifest.json.

### Step 1: Get latest PocketMine-MP release

```bash
curl -s -H "Accept: application/vnd.github+json" \
  https://api.github.com/repos/pmmp/PocketMine-MP/releases/latest | jq -r '.tag_name'
```

**Ejemplo de output:**
```
5.43.1
```

**¿Qué obtiene?**
- Última versión publicada en GitHub
- O versión forzada si pasas `force_version` en manual

---

### Step 2: Check if version already in manifest

```bash
jq --arg v "5.43.1" '[.versions[].id] | contains([$v])' manifest.json
```

**Output:**
- `true` → Ya existe, skip los demás jobs
- `false` → Nueva versión, continúa

---

### Step 3: Get release details

Extrae información del release:

```bash
curl -s "https://api.github.com/repos/pmmp/PocketMine-MP/releases/tags/5.43.1" | \
  jq '.body' | grep -oP 'Bedrock\s+\K[0-9]+\.[0-9]+\.[0-9]+'
```

**Ejemplo:**
- Release body: `"Supports Bedrock 1.21.51"`
- Extrae: `1.21.51` → MC version

---

## 🚀 Job 2: `generate-stubs` (condicional)

**Ejecuta solo si `needs_update == 'true'`**

```yaml
if: needs.check-releases.outputs.needs_update == 'true'
```

### Genera los stubs

```bash
python3 generator/generate.py \
  --version="5.43.1" \
  --workdir="generator/workdir" \
  --output="generator/output" \
  --clean
```

**Output:**
```
a992d1a6d33d65b9117ec7cb6a76606d9d41a75d2de57ffb09e87f6af63a841
```

El SHA256 se captura y pasa al siguiente job:

```yaml
echo "sha256=$SHA256" >> $GITHUB_OUTPUT
```

---

## 📝 Job 3: `auto-update` (condicional)

**Ejecuta solo después de `generate-stubs`:**

```yaml
needs: [check-releases, generate-stubs]
if: needs.check-releases.outputs.needs_update == 'true'
```

### Step 1: Create feature branch

```bash
BRANCH_NAME="feat/update-pm-5431"  # 5.43.1 sin puntos
git checkout -b "$BRANCH_NAME"
```

---

### Step 2: Update manifest

Actualiza `manifest.json` con la nueva versión:

```json
{
  "id": "5.43.1",
  "mc_version": "1.21.51",
  "api_version": "6.0.0",
  "status": "stable",
  "stubs": {
    "url": "https://github.com/.../releases/download/5.43.1/stubs-5.43.1.zip",
    "checksum_sha256": "a992d1a..."
  },
  "date": "2026-05-22T18:20:00Z"
}
```

---

### Step 3: Commit y Push

```bash
git add manifest.json
git commit -m "feat: add PocketMine-MP 5.43.1

- Auto-update via GitHub Actions
- MC version: 1.21.51
- SHA256: a992d1a...
- Stubs generated and verified"

git push origin feat/update-pm-5431
```

---

### Step 4: Create Pull Request

Usa `actions/github-script@v7` para crear PR automático:

```javascript
await github.rest.pulls.create({
  title: "🎉 feat: Add PocketMine-MP 5.43.1",
  head: "feat/update-pm-5431",
  base: "main",
  body: "Descripción formateada con detalles...",
  labels: ["automated", "version-update"]
})
```

**Resultado en GitHub:**

```
PR #123
🎉 feat: Add PocketMine-MP 5.43.1

## 🚀 Automated Version Update

### 📋 Details
| Field | Value |
|-------|-------|
| **Version** | `5.43.1` |
| **MC Version** | `1.21.51` |
| **Stubs SHA256** | `a992d1a...` |

### ✅ Automated Checks
- [x] Stubs generated successfully
- [x] SHA256 verified
- [x] Manifest entry created

### 🔍 Review Checklist
- [ ] Verify MC/API versions are correct
- [ ] Validate against official changelog
- [ ] Test stubs with IDE

[Labels: automated, version-update]
```

---

## 📊 Inputs (Manual Trigger)

Si ejecutas manualmente desde **Actions → Generate Stubs → Run workflow**:

| Input | Tipo | Default | Descripción |
|-------|------|---------|-------------|
| `force_version` | string | - | Fuerza verificación de versión específica |
| `auto_pr` | boolean | `true` | Crea PR automáticamente |

**Ejemplo:**
```
force_version = "5.42.1"
auto_pr = true
```

---

## 🔐 Outputs (Pasados entre jobs)

```yaml
check-releases outputs:
  - version: "5.43.1"
  - needs_update: true
  - mc_version: "1.21.51"

generate-stubs outputs:
  - sha256: "a992d1a..."
```

Usados así:

```yaml
${{ needs.check-releases.outputs.version }}
${{ needs.generate-stubs.outputs.sha256 }}
```

---

## ⏱️ Tiempos Estimados

| Job | Tiempo | Notas |
|-----|--------|-------|
| check-releases | ~30 seg | Consultas a API |
| generate-stubs | ~2-3 min | Generación de stubs |
| auto-update | ~1 min | Push y PR |
| **TOTAL** | **~4 min** | Sin contar caché |

---

## 🛡️ Validaciones

El workflow incluye validaciones importantes:

```bash
# 1. ¿Versión existe?
curl -s "$URL" | jq '.tag_name'

# 2. ¿Ya está en manifest?
jq '[.versions[].id] | contains([...])'

# 3. ¿ZIP se generó?
[ -f "stubs-$VERSION.zip" ]

# 4. ¿ZIP tiene archivos?
unzip -l "$ZIP" | grep -c "\.php$"
```

Si fallan, el workflow **se detiene** y notifica el error.

---

## 🚀 Ejemplo de Ejecución Completa

### Escenario: Nueva versión 5.43.1 detectada

```
[00:00 UTC] ⏰ Cron trigger activado

Job 1: check-releases
  ✓ Obtiene latest: 5.43.1
  ✓ Check manifest: NO existe
  ✓ Extrae MC version: 1.21.51
  → needs_update = true

Job 2: generate-stubs (paralelo)
  ✓ Setup Python 3.11, PHP 8.2
  ✓ Genera stubs → SHA256: a992d1a...
  ✓ Verifica ZIP (228 archivos, 15 MB)
  → output: sha256

Job 3: auto-update
  ✓ Crea rama feat/update-pm-5431
  ✓ Actualiza manifest.json
  ✓ Commit: "feat: add PocketMine-MP 5.43.1"
  ✓ Push origin feat/update-pm-5431
  ✓ Crea PR #123
  → Espera revisión manual
```

---

## ⚠️ Flujo si la versión ya existe

```
[00:00 UTC] ⏰ Cron trigger activado

Job 1: check-releases
  ✓ Obtiene latest: 5.43.1
  ✓ Check manifest: YA EXISTE
  → needs_update = false

Job 2, 3: SKIPPED (no se ejecutan)
  ℹ️  Workflow se detiene silenciosamente
```

---

## 🔄 Cómo integrar con `pocketmine-manifest`

Este workflow es complementario. Se integra así:

```
1. pocketmine-stubs (este repo)
   ├─ Detecta nueva versión
   ├─ Genera stubs
   └─ Crea PR aquí con SHA256

2. Mantenedor revisa PR
   ├─ Verifica cambios
   ├─ Merge PR
   └─ Release publicado con stubs

3. pocketmine-manifest (otro repo)
   ├─ Detecta nuevo release en pocketmine-stubs
   ├─ Obtiene SHA256
   └─ Actualiza manifest.json
```

---

## 📌 Próximos Pasos (Opcional)

Para full automation podrías agregar:

1. **Auto-merge de PRs:**
   ```yaml
   - uses: pascalgn/automerge-action@v0.15
     if: github.actor == 'github-actions[bot]'
   ```

2. **Notificaciones a Discord:**
   ```yaml
   - uses: sarisia/actions-status-discord@v1
   ```

3. **Create tag automático:**
   ```bash
   git tag -a "v$VERSION"
   git push origin --tags
   ```

---

¿Necesitas algún ajuste o explicación adicional sobre este workflow?
