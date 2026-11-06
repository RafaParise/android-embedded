package br.embeeded.papel;

import android.accessibilityservice.AccessibilityService;
import android.content.res.Resources;
import android.view.accessibility.AccessibilityEvent;

/**
 * Faz o papel rolante seguir a pagina EXATA da tela inicial da Samsung (inclusive quando o botao
 * Inicio volta para a primeira pagina, que o toque nao ve) e conta as paginas de verdade.
 *
 * So recebe um tipo de evento (rolagem) de um so app (com.sec.android.app.launcher) e nao le o
 * conteudo de nenhuma tela (canRetrieveWindowContent=false). Medido em 05/11 com `uiautomator events`:
 * a area de trabalho (com.android.launcher3.PagedView) anuncia ScrollX de 0 a MaxScrollX (2133 com 4 paginas,
 * ou seja ~711 px por pagina numa tela de 720). Medido em 05/11 21:27 (gravacao da tela): o aviso chega so quando
 * a pagina encaixa, ~0,5 s depois; por isso o papel segue o dedo e usa este aviso para acertar a posicao final.
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
        int largura = Resources.getSystem().getDisplayMetrics().widthPixels;
        // paginas reais: cada pagina rola quase uma largura de tela (711 de 720 no A12); deitado nao ha rolagem do papel
        int paginas = largura > 0 ? Math.max(2, Math.min(12, Math.round(max / (largura * 0.988f)) + 1)) : 0;
        Papel.pagina(Math.max(0f, Math.min(1f, e.getScrollX() / (float) max)), paginas);
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
