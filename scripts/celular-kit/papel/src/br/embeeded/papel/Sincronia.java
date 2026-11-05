package br.embeeded.papel;

import android.accessibilityservice.AccessibilityService;
import android.view.accessibility.AccessibilityEvent;

/**
 * Faz o papel rolante seguir a pagina EXATA da tela inicial da Samsung (inclusive quando o botao
 * Inicio volta para a primeira pagina, que o toque nao ve).
 *
 * So recebe um tipo de evento (rolagem) de um so app (com.sec.android.app.launcher) e nao le o
 * conteudo de nenhuma tela (canRetrieveWindowContent=false). Medido em 05/11 com `uiautomator events`:
 * a area de trabalho (com.android.launcher3.PagedView) anuncia ScrollX de 0 a MaxScrollX (2133 com 4 paginas).
 * Liga e desliga em Configuracoes > Acessibilidade > Apps instalados > Papel rolante, ou
 * `python scripts/papel-rolante.py sincronia ligar|desligar` no PC.
 */
public class Sincronia extends AccessibilityService {
    @Override
    protected void onServiceConnected() {
        Papel.seguePaginas = true;
    }

    @Override
    public void onAccessibilityEvent(AccessibilityEvent e) {
        if (e == null || e.getEventType() != AccessibilityEvent.TYPE_VIEW_SCROLLED) return;
        CharSequence classe = e.getClassName();
        if (classe == null || !"com.android.launcher3.PagedView".contentEquals(classe)) return;
        int max = e.getMaxScrollX();
        if (max <= 0) return;
        Papel.pagina(Math.max(0f, Math.min(1f, e.getScrollX() / (float) max)));
    }

    @Override
    public void onInterrupt() {
    }

    @Override
    public boolean onUnbind(android.content.Intent i) {
        Papel.seguePaginas = false;
        return super.onUnbind(i);
    }
}
