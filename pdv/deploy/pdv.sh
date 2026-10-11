#!/usr/bin/env bash
# Operação do PDV Restaurantes numa VPS (Ubuntu/Debian com Docker).
#
#   ./deploy/pdv.sh instalar [dominio]   primeira instalação: cria o .env, sobe tudo com HTTPS
#   ./deploy/pdv.sh atualizar            backup, git pull, reconstrói e verifica
#   ./deploy/pdv.sh verificar            saúde, HTTPS, webhook fechado, WhatsApp, logs sem telefone, disco
#   ./deploy/pdv.sh backup               banco + sessões do WhatsApp em ./backups (guarda os 14 últimos)
#   ./deploy/pdv.sh restaurar <banco.dump> [sessoes.tgz]
#   ./deploy/pdv.sh relatorio [dias]     números do piloto (padrão: 7 dias)
#   ./deploy/pdv.sh logs [serviço]       últimos logs
#
# Rode sempre de dentro da pasta pdv/ do repositório.
# Variáveis opcionais: BACKUP_DIR, BACKUP_MANTER, ALERTA_URL (ex.: https://ntfy.sh/seu-topico),
# VERIFICAR_INSEGURO=1 (aceita certificado de teste; só para DOMINIO=localhost).
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$RAIZ"

COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.prod.yml)
BACKUP_DIR="${BACKUP_DIR:-$RAIZ/backups}"
BACKUP_MANTER="${BACKUP_MANTER:-14}"
# Telefone brasileiro com país (55 + DDD + número), sem encostar em outros dígitos (RN-10)
RE_TELEFONE='(^|[^0-9])55[0-9]{10,11}([^0-9]|$)'

ok() { printf '  \033[32m✓\033[0m %s\n' "$*"; }
aviso() { printf '  \033[33m!\033[0m %s\n' "$*"; }
falha() { printf '  \033[31m✗\033[0m %s\n' "$*"; FALHAS=$((FALHAS + 1)); }
morrer() { printf 'erro: %s\n' "$*" >&2; exit 1; }
FALHAS=0

valor_env() {
  # Lê uma variável do .env sem executar o arquivo
  sed -n "s/^$1=//p" .env 2>/dev/null | tail -n 1
}

exigir_docker() {
  command -v docker >/dev/null || morrer "Docker não encontrado. Instale com: curl -fsSL https://get.docker.com | sudo sh"
  docker compose version >/dev/null 2>&1 || morrer "Docker Compose v2 não encontrado (docker compose version)."
  docker info >/dev/null 2>&1 || morrer "sem acesso ao Docker. Rode com sudo ou adicione seu usuário ao grupo docker."
}

exigir_env() {
  [[ -f .env ]] || morrer "falta o .env. Rode primeiro: ./deploy/pdv.sh instalar"
  [[ -n "$(valor_env DOMINIO)" ]] || morrer "DOMINIO vazio no .env"
}

# ---------------------------------------------------------------- instalar

dominio_valido() {
  [[ "$1" == "localhost" || "$1" =~ ^([a-z0-9]([a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,}$ ]]
}

sugerir_dominio() {
  local ip
  ip="$(curl -fsS --max-time 5 https://api.ipify.org 2>/dev/null || true)"
  [[ "$ip" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]] && echo "${ip//./-}.sslip.io"
}

criar_env() {
  local dominio="$1"
  if [[ -z "$dominio" ]]; then
    local sugestao
    sugestao="$(sugerir_dominio)"
    echo "Domínio do painel (precisa apontar para o IP desta VPS)."
    [[ -n "$sugestao" ]] && echo "Sem domínio próprio, use: $sugestao"
    read -r -p "Domínio${sugestao:+ [$sugestao]}: " dominio
    dominio="${dominio:-$sugestao}"
  fi
  dominio="$(echo "$dominio" | tr '[:upper:]' '[:lower:]')"
  dominio_valido "$dominio" || morrer "domínio inválido: '$dominio'"
  command -v openssl >/dev/null || morrer "openssl não encontrado (sudo apt install openssl)"
  umask 077
  cat > .env <<EOF
# Gerado por deploy/pdv.sh em $(date -Iseconds). Não versionar. Guarde uma cópia em local seguro.
DOMINIO=$dominio
POSTGRES_PASSWORD=$(openssl rand -hex 24)
JWT_SECRET=$(openssl rand -hex 32)
GATEWAY_TOKEN=$(openssl rand -hex 24)
CORS_ORIGENS=
EOF
  chmod 600 .env
  ok ".env criado com segredos novos para $dominio"
}

cmd_instalar() {
  exigir_docker
  if [[ -f .env ]]; then
    ok ".env já existe; mantendo os segredos atuais"
    [[ -n "$(valor_env DOMINIO)" ]] || morrer "o .env existente não tem DOMINIO; acrescente DOMINIO=seu.dominio"
  else
    criar_env "${1:-}"
  fi
  echo "Construindo e subindo (a primeira vez leva alguns minutos)..."
  "${COMPOSE[@]}" up -d --build --wait --wait-timeout 600
  ok "serviços no ar"
  cmd_verificar || true
  echo
  echo "Painel: https://$(valor_env DOMINIO)"
  echo "Próximos passos: cadastre o restaurante, monte o cardápio e os horários, conecte o WhatsApp."
  echo "Agende backup e verificação: veja deploy/crontab.exemplo"
}

# ---------------------------------------------------------------- atualizar

cmd_atualizar() {
  exigir_docker
  exigir_env
  cmd_backup
  if git -C "$RAIZ" rev-parse --git-dir >/dev/null 2>&1; then
    git -C "$RAIZ" pull --ff-only
  else
    aviso "pasta sem git: atualizando só a partir dos arquivos atuais"
  fi
  "${COMPOSE[@]}" up -d --build --wait --wait-timeout 600
  ok "serviços atualizados (as migrações do banco rodam ao subir a API)"
  cmd_verificar
}

# ---------------------------------------------------------------- verificar

curl_https() {
  local extra=()
  [[ "${VERIFICAR_INSEGURO:-0}" == "1" ]] && extra=(-k)
  curl -sS --max-time 10 "${extra[@]}" "$@"
}

cmd_verificar() {
  exigir_env
  local dominio
  dominio="$(valor_env DOMINIO)"
  FALHAS=0
  echo "Verificando https://$dominio"

  local servico estado
  for servico in db api wa-gateway web caddy; do
    estado="$("${COMPOSE[@]}" ps --format '{{.Service}} {{.State}} {{.Health}}' 2>/dev/null | awk -v s="$servico" '$1 == s {print $2, $3}')"
    case "$estado" in
      "running healthy" | "running ") ok "$servico: rodando" ;;
      running*) aviso "$servico: rodando ($estado)" ;;
      *) falha "$servico: ${estado:-parado}" ;;
    esac
  done

  if curl_https -f "https://$dominio/api/saude" 2>/dev/null | grep -q '"ok":true'; then
    ok "API responde por HTTPS"
  else
    falha "API não responde em https://$dominio/api/saude"
  fi

  local codigo
  codigo="$(curl_https -o /dev/null -w '%{http_code}' -X POST "https://$dominio/api/canal/webhook" 2>/dev/null || true)"
  if [[ "$codigo" == "404" ]]; then ok "webhook interno fechado para a internet"; else falha "webhook respondeu $codigo (esperado 404)"; fi

  codigo="$(curl -sS --max-time 10 -o /dev/null -w '%{http_code}' "http://$dominio/" 2>/dev/null || true)"
  if [[ "$codigo" =~ ^30[178]$ ]]; then ok "HTTP redireciona para HTTPS"; else aviso "HTTP respondeu $codigo (esperado redirecionar)"; fi

  local conexoes
  conexoes="$("${COMPOSE[@]}" exec -T db psql -U pdv -d pdv -tA -F ' ' -c \
    "SELECT coalesce(c.status, 'nunca_conectado'), count(*) FROM restaurante r
     LEFT JOIN conexao_whatsapp c ON c.restaurante_id = r.id GROUP BY 1 ORDER BY 1" 2>/dev/null || true)"
  if [[ -z "$conexoes" ]]; then
    aviso "nenhum restaurante cadastrado ainda"
  else
    while read -r status quantos; do
      case "$status" in
        conectado) ok "WhatsApp conectado: $quantos restaurante(s)" ;;
        nunca_conectado) aviso "WhatsApp nunca conectado: $quantos restaurante(s)" ;;
        *) falha "WhatsApp $status: $quantos restaurante(s) — gere um novo QR code no painel" ;;
      esac
    done <<< "$conexoes"
  fi

  if "${COMPOSE[@]}" logs --no-color --since 24h api wa-gateway web db 2>/dev/null | grep -Eq "$RE_TELEFONE"; then
    falha "telefone completo encontrado nos logs das últimas 24 h (RN-10) — investigue antes de seguir"
  else
    ok "logs das últimas 24 h sem telefone completo"
  fi

  local uso
  uso="$(df -P "$RAIZ" | awk 'NR == 2 {gsub("%", "", $5); print $5}')"
  if [[ "$uso" -ge 90 ]]; then falha "disco ${uso}% cheio"; elif [[ "$uso" -ge 80 ]]; then aviso "disco ${uso}% cheio"; else ok "disco ${uso}% usado"; fi

  if [[ "$FALHAS" -gt 0 ]]; then
    echo "$FALHAS problema(s) encontrado(s)."
    if [[ -n "${ALERTA_URL:-}" ]]; then
      curl -sS --max-time 10 -d "PDV $dominio: $FALHAS problema(s) na verificação. Rode ./deploy/pdv.sh verificar" "$ALERTA_URL" >/dev/null || true
    fi
    return 1
  fi
  echo "Tudo certo."
}

# ---------------------------------------------------------------- backup e restauração

cmd_backup() {
  exigir_env
  mkdir -p "$BACKUP_DIR"
  chmod 700 "$BACKUP_DIR"
  umask 077
  local quando banco sessoes
  quando="$(date +%Y%m%d-%H%M%S)"
  banco="$BACKUP_DIR/pdv-$quando.dump"
  sessoes="$BACKUP_DIR/sessoes-$quando.tgz"
  "${COMPOSE[@]}" exec -T db pg_dump -U pdv -d pdv -Fc > "$banco.tmp"
  mv "$banco.tmp" "$banco"
  "${COMPOSE[@]}" exec -T wa-gateway tar czf - -C /data . > "$sessoes.tmp"
  mv "$sessoes.tmp" "$sessoes"
  ok "backup: $banco ($(du -h "$banco" | cut -f1)) e $sessoes"
  # Mantém só os mais recentes; backups têm dados pessoais (RN-10)
  local tipo
  for tipo in pdv sessoes; do
    find "$BACKUP_DIR" -maxdepth 1 -name "$tipo-*" -type f -printf '%T@ %p\n' | sort -rn |
      tail -n +"$((BACKUP_MANTER + 1))" | cut -d' ' -f2- | xargs -r rm -f
  done
}

cmd_restaurar() {
  exigir_docker
  exigir_env
  local banco="${1:-}" sessoes="${2:-}"
  [[ -f "$banco" ]] || morrer "informe o arquivo do banco: ./deploy/pdv.sh restaurar backups/pdv-AAAAMMDD-HHMMSS.dump [sessoes.tgz]"
  [[ -z "$sessoes" || -f "$sessoes" ]] || morrer "arquivo de sessões não encontrado: $sessoes"
  echo "Isto SUBSTITUI todos os dados atuais pelo backup $banco."
  if [[ "${CONFIRMAR:-}" != "RESTAURAR" ]]; then
    read -r -p "Digite RESTAURAR para continuar: " CONFIRMAR
    [[ "$CONFIRMAR" == "RESTAURAR" ]] || morrer "cancelado"
  fi
  "${COMPOSE[@]}" up -d --wait db
  "${COMPOSE[@]}" stop api wa-gateway
  "${COMPOSE[@]}" exec -T db pg_restore -U pdv -d pdv --clean --if-exists --no-owner < "$banco"
  ok "banco restaurado"
  if [[ -n "$sessoes" ]]; then
    "${COMPOSE[@]}" run --rm --no-deps -T --entrypoint sh wa-gateway -c 'find /data -mindepth 1 -delete && tar xzf - -C /data' < "$sessoes"
    ok "sessões do WhatsApp restauradas"
  fi
  "${COMPOSE[@]}" up -d --wait --wait-timeout 600
  ok "serviços no ar"
}

# ---------------------------------------------------------------- relatório e logs

cmd_relatorio() {
  exigir_env
  local dias="${1:-7}"
  [[ "$dias" =~ ^[0-9]+$ && "$dias" -ge 1 ]] || morrer "dias deve ser um número inteiro >= 1"
  "${COMPOSE[@]}" exec -T db psql -U pdv -d pdv -v ON_ERROR_STOP=1 -v dias="$dias" < "$RAIZ/deploy/relatorio.sql"
}

cmd_logs() {
  "${COMPOSE[@]}" logs --no-color --tail 200 "$@"
}

# ---------------------------------------------------------------- principal

comando="${1:-}"
shift || true
case "$comando" in
  instalar) cmd_instalar "$@" ;;
  atualizar) cmd_atualizar ;;
  verificar) cmd_verificar ;;
  backup) exigir_docker; cmd_backup ;;
  restaurar) cmd_restaurar "$@" ;;
  relatorio) exigir_docker; cmd_relatorio "$@" ;;
  logs) cmd_logs "$@" ;;
  *) sed -n '2,14p' "$0" | sed 's/^# \{0,1\}//'; exit 2 ;;
esac
