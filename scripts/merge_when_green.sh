#!/bin/bash
# Mergeia um PR SOMENTE se o CI terminar verde. Qualquer outra coisa (vermelho, cancelado, sem confirmação) interrompe.
# Uso: bash scripts/merge_when_green.sh <numero-do-PR>
# Existe porque, em 2026-10-03, um merge foi feito com o CI vermelho (o comando seguinte não olhou o resultado do anterior).
set -euo pipefail
PR="${1:?informe o número do PR}"
for _ in $(seq 1 40); do
  s=$(gh pr checks "$PR" 2>&1 || true)
  if echo "$s" | grep -qE "pending|in_progress|queued|no checks"; then sleep 15; continue; fi
  break
done
echo "$s" | cut -c1-60
if echo "$s" | grep -qE "fail|cancel"; then echo "CI VERMELHO: NÃO VOU MERGEAR #$PR" >&2; exit 1; fi
if ! echo "$s" | grep -q "Engine Python.*pass" || ! echo "$s" | grep -q "Web, Worker e shared.*pass"; then
  echo "CI sem confirmação completa: NÃO VOU MERGEAR #$PR" >&2; exit 1
fi
gh pr merge "$PR" --merge
echo "MERGEADO #$PR (CI verde)"
