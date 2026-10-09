#!/bin/sh
# Gera um "set_real_ip_from" para cada rede em PROXY_CONFIAVEL (lista separada por vírgula).
# Roda antes do envsubst da imagem; o arquivo vale no contexto http (REV-18, REV-24).
set -eu
saida=${PROXY_CONF_SAIDA:-/etc/nginx/conf.d/00-proxy-confiavel.conf}
: > "$saida"
for rede in $(echo "${PROXY_CONFIAVEL:-}" | tr ',' ' '); do
  # Só IP ou rede (IPv4/IPv6 com máscara); qualquer outra coisa poderia injetar diretivas no nginx
  case "$rede" in
    *[!0-9a-fA-F:./]*) echo "PROXY_CONFIAVEL inválido: $rede" >&2; exit 1 ;;
  esac
  echo "set_real_ip_from $rede;" >> "$saida"
done
echo "real_ip_header X-Forwarded-For;" >> "$saida"
echo "real_ip_recursive on;" >> "$saida"
