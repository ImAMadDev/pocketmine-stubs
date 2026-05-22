# 🤖 Automatización: Check New PocketMine-MP Releases

Este workflow automatiza la detección de nuevas versiones de PocketMine-MP y genera stubs automáticamente cada 12 horas, creando GitHub Releases.

## 📅 Scheduled Automation

El workflow se ejecuta **automáticamente cada 12 horas** mediante cron, pero también puede ejecutarse manualmente.

### Trigger: `schedule`

```yaml
schedule:
  - cron: "0 */12 * * *"
```

**¿Cuándo se ejecuta?**
- Cada 12 horas: `0:00, 12:00 UTC`

---

## 🎯 Flujo de Ejecución

```
┌────────────────────────────────────────────────────────────────┐
│ Cada 12 horas o manual (workflow_dispatch)                    │
└───────────────────────┬────────────────────────────────────────┘
                        │
                        ▼
        ┌───────────────────────────────────┐
        │ Job 1: check-releases             │
        │ ├─ ¿Nueva versión en PMMP?        │
        │ ├─ ¿Ya generado en este repo?     │
        │ └─ Extraer MC version             │
        └───────────────┬───────────────────┘
                        │
                        ▼
            ¿needs_generation = true?
                        │
        ┌───────────────┴───────────────┐
        │ NO                            │ SÍ
        ▼                               ▼
    (Stop)                  ┌──────────────────────────┐
                            │ Job 2: generate-stubs    │
                            │ ├─ python generate.py    │
                            │ ├─ SHA256                │
                            │ ├─ Verificar ZIP         │
                            │ └─ Crear Release         │
                            └────────┬─────────────────┘
                                     │
                                     ▼
                        ┌────────────────────────────┐
                        │ ✅ Release creado          │
                        │    Stubs disponibles       │
                        └────────────────────────────┘
```

---

## 🔍 Job 1: `check-releases`

**¿Qué hace?**

Detecta nuevas versiones de PocketMine-MP y verifica si ya existen en este repositorio.

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

### Step 2: Check if stubs already exist

```bash
curl -s -o /dev/null -w "%{http_code}" \
  "https://api.github.com/repos/$REPO/releases/tags/5.43.1"
```

**Output:**
- `200` → Ya existen, skip los demás jobs
- `404` → Nueva versión, genera stubs

---

### Step 3: Get release details from PMMP

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

**Ejecuta solo si `needs_generation == 'true'`**

```yaml
if: needs.check-releases.outputs.needs_generation == 'true'
```

### Setup y Caché

```yaml
- uses: actions/cache@v4
  with:
    path: |
      generator/workdir/pocketmine_phar
      generator/workdir/phpstorm_stubs_fork
    key: stubs-downloads-${{ version }}
```

Cachea descargas para ejecuciones futuras.

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

El SHA256 se captura:

```yaml
echo "sha256=$SHA256" >> $GITHUB_OUTPUT
```

### Verifica archivos

- ✅ ZIP existe
- ✅ Stats JSON existe
- ✅ Tamaño correcto

### Sube artifacts

```yaml
- uses: actions/upload-artifact@v4
  with:
    name: stubs-5.43.1
    path: generator/output/stubs-*.zip
    retention-days: 5
```

### Crea GitHub Release

```yaml
- uses: softprops/action-gh-release@v2
  with:
    tag_name: 5.43.1
    name: "Stubs PocketMine-MP 5.43.1"
    files: |
      generator/output/stubs-5.43.1.zip
      generator/output/stats-5.43.1.json
    body: |
      ## 📦 Stubs para PocketMine-MP 5.43.1
      
      | Campo | Valor |
      |-------|-------|
      | **Versión PM** | `5.43.1` |
      | **Versión MC** | `1.21.51` |
      | **SHA256** | `a992d1a...` |
```

---

## 📊 Inputs (Manual Trigger)

Si ejecutas manualmente desde **Actions → Check New PocketMine-MP Releases → Run workflow**:

| Input | Tipo | Default | Descripción |
|-------|------|---------|-------------|
| `force_version` | string | - | Fuerza generación para versión específica |

**Ejemplo:**
```
force_version = "5.42.1"
```

---

## 🔐 Outputs (Pasados entre jobs)

```yaml
check-releases outputs:
  - version: "5.43.1"
  - needs_generation: true
  - mc_version: "1.21.51"

generate-stubs outputs:
  - sha256: "a992d1a..."
```

Usados así:

```yaml
${{ needs.check-releases.outputs.version }}
${{ steps.generate.outputs.sha256 }}
```

---

## ⏱️ Tiempos Estimados

| Fase | Tiempo | Notas |
|------|--------|-------|
| Check releases | ~30 seg | Consultas a APIs |
| Generate stubs | ~2-3 min | Parsing + generación |
| Create release | ~1 min | Upload + release |
| **TOTAL** | **~4 min** | Con caché activa |

---

## 🛡️ Validaciones

El workflow incluye validaciones importantes:

```bash
# 1. ¿Última versión en PMMP?
curl -s "$URL" | jq '.tag_name'

# 2. ¿Ya existe en este repo?
curl -s -o /dev/null -w "%{http_code}" "$RELEASE_URL"

# 3. ¿ZIP se generó?
[ -f "stubs-$VERSION.zip" ]

# 4. ¿Stats se generó?
[ -f "stats-$VERSION.json" ]
```

Si fallan, el workflow **se detiene**.

---

## 🚀 Ejemplo de Ejecución Completa

### Escenario: Nueva versión 5.43.1 detectada

```
[00:00 UTC] ⏰ Cron trigger activado

Job 1: check-releases
  ✓ Obtiene latest: 5.43.1
  ✓ Check releases: NOT_FOUND (404)
  ✓ Extrae MC version: 1.21.51
  → needs_generation = true

Job 2: generate-stubs
  ✓ Setup Python 3.11, PHP 8.2
  ✓ Restaura caché
  ✓ Genera stubs → SHA256: a992d1a...
  ✓ Verifica ZIP y Stats
  ✓ Sube artifacts (5 días)
  ✓ Crea Release con archivos
  → Release publicado

[04:00] ✅ Workflow completado exitosamente
```

---

## ⚠️ Flujo si la versión ya existe

```
[00:00 UTC] ⏰ Cron trigger activado

Job 1: check-releases
  ✓ Obtiene latest: 5.43.1
  ✓ Check releases: FOUND (200)
  → needs_generation = false

Job 2: SKIPPED (no se ejecuta)
  ℹ️  Workflow se detiene silenciosamente
```

---

## 🔄 Integración con otros repositorios

### pocketine-stubs (este repo)
```
Detecta nueva versión
       ↓
   Genera stubs
       ↓
  Crea Release
       ↓
Publica ZIP + SHA256
```

### pocketmine-manifest (otro repo)
```
Detecta Release en pocketmine-stubs
       ↓
    Obtiene SHA256
       ↓
  Actualiza manifest
       ↓
    Publica cambios
```

---

## 📌 Próximos Pasos (Opcional)

Para enhanced automation:

1. **Discord Notifications:**
   ```yaml
   - uses: sarisia/actions-status-discord@v1
     with:
       webhook_url: ${{ secrets.DISCORD_WEBHOOK }}
   ```

2. **Auto-trigger pocketmine-manifest:**
   ```yaml
   - uses: peter-evans/repository-dispatch@v2
     with:
       repository: pocketide/pocketmine-manifest
       event-type: stubs-updated
       client-payload: '{"version": "${{ needs.check-releases.outputs.version }}", "sha256": "${{ steps.generate.outputs.sha256 }}"}'
   ```

3. **Automatic tag creation:**
   ```bash
   git tag -a "v$VERSION"
   git push origin --tags
   ```

---

## 📝 Resumen

| Aspecto | Detalles |
|---------|----------|
| **Trigger** | Cron cada 12h + manual |
| **Verificación** | HTTP check a releases |
| **Generación** | Python + PHP sin deps |
| **Caché** | Acelera re-ejecuciones |
| **Release** | Auto-publish a GitHub |
| **Artifacts** | 5 días retenidos |
| **Tiempo** | ~4 minutos total |

---

¿Preguntas o cambios adicionales?
