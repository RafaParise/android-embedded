package br.embeeded.papel;

import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.LightingColorFilter;
import android.graphics.Matrix;
import android.graphics.Paint;
import android.graphics.PixelFormat;
import android.graphics.Point;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.service.wallpaper.WallpaperService;
import android.util.Log;
import android.view.Display;
import android.view.MotionEvent;
import android.view.SurfaceHolder;
import android.view.VelocityTracker;
import android.view.ViewConfiguration;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileReader;
import java.lang.reflect.Method;

/**
 * Papel de parede rolante (pedido do Rafael, 05/11/2026), como nos Samsung antigos.
 *
 * Em pe: a imagem larga ocupa a altura da tela e anda para o lado quando o dedo arrasta
 * na tela inicial, com "paginas" que encaixam. Deitado: a imagem inteira aparece, sem corte,
 * com um fundo desfocado da propria imagem nas bordas.
 *
 * Medido no A12 em 05/11: a tela inicial da Samsung (One UI) nao informa a rolagem ao papel de
 * parede (mLastWallpaperX fica em 0.5) e, deitada, empurra o papel 321 px para cima
 * (mLastWallpaperDisplayOffsetY=-321). Por isso:
 *  - o movimento vem do toque, que o Android repassa ao papel de parede;
 *  - o deslocamento vem do PC: papel-rolante.py le o dumpsys e grava desloc.txt ("X Y"; medido
 *    -321 na vertical, deitado e em pe); o toque NAO revela isso (getRawY - getY deu 0);
 *  - a superficie fica maior que a tela o bastante para cobrir o deslocamento nos dois sentidos,
 *    e o desenho vai so na parte visivel (Android: janela em -(sobra * offset) + deslocamento).
 * Se a tela inicial informar a rolagem (outro launcher), ela vence.
 *
 * Leve de proposito: nada roda em laco; so desenha quando o dedo mexe, a tela gira ou volta a aparecer.
 * Imagem: Android/data/br.embeeded.papel/files/papel.jpg (ou .png); paginas: paginas.txt (2 a 9, padrao 4).
 */
public class Papel extends WallpaperService {
    static final String TAG = "PapelRolante";

    private final java.util.List<Motor> motores = new java.util.ArrayList<>();
    private static volatile Papel viva;
    /** true enquanto o servico Sincronia (acessibilidade) estiver ligado. */
    static volatile boolean seguePaginas;

    @Override
    public void onCreate() {
        super.onCreate();
        viva = this;
    }

    @Override
    public void onDestroy() {
        if (viva == this) viva = null;
        super.onDestroy();
    }

    /** Posicao exata da tela inicial (0 = primeira pagina, 1 = ultima), vinda da Sincronia. */
    static void pagina(float p) {
        Papel s = viva;
        if (s == null) return;
        for (Motor m : new java.util.ArrayList<>(s.motores)) m.fila.post(() -> m.vaiPara(p));
    }

    @Override
    public Engine onCreateEngine() {
        return new Motor();
    }

    /** A tela girou: com tamanho fixo o Android nao avisa a superficie, entao cada motor se reajusta. */
    @Override
    public void onConfigurationChanged(android.content.res.Configuration c) {
        super.onConfigurationChanged(c);
        for (Motor m : new java.util.ArrayList<>(motores)) m.fila.post(m::reajusta);
    }

    class Motor extends Engine implements Runnable {
        final Handler fila = new Handler(Looper.getMainLooper());
        private final Paint tinta = new Paint(Paint.FILTER_BITMAP_FLAG);
        private final Paint escuro = new Paint(Paint.FILTER_BITMAP_FLAG);
        private final Matrix mat = new Matrix();
        private final Point tela = new Point();
        private int deslX, deslY;
        private Bitmap img, fundo;
        private long lido = -1, deslocLido = -1;
        private int largura, altura, folga = 16;
        private int paginas = 4;
        private boolean tamanhoLivre;
        private float xOff = 0.5f, yOff = 0.5f;
        private float pos = 0f;
        private boolean lancadorRola;
        private float x0, y0, pos0;
        private boolean decidido, arrastando;
        private VelocityTracker vel;
        private boolean animando;
        private float animDe, animAlvo;
        private long animIni;

        @Override
        public void onCreate(SurfaceHolder holder) {
            super.onCreate(holder);
            setTouchEventsEnabled(true);
            setOffsetNotificationsEnabled(true);
            holder.setFormat(PixelFormat.RGB_565);
            escuro.setColorFilter(new LightingColorFilter(0x707070, 0));
            folga = ViewConfiguration.get(Papel.this).getScaledTouchSlop();
            try {
                Method m = Engine.class.getDeclaredMethod("setFixedSizeAllowed", boolean.class);
                m.setAccessible(true);
                m.invoke(this, true);
                tamanhoLivre = true;
            } catch (Throwable t) {
                Log.w(TAG, "sem setFixedSizeAllowed: " + t);
            }
            carrega();
            ajustaTamanho();
            motores.add(this);
        }

        void vaiPara(float p) {
            if (arrastando || lancadorRola) return;
            if (Math.abs(p - (animando ? animAlvo : pos)) < 0.002f) return;
            anima(p);
        }

        void reajusta() {
            medeTela();
            if (!ajustaTamanho()) desenha();
        }

        @Override
        public void onDestroy() {
            motores.remove(this);
            fila.removeCallbacksAndMessages(null);
            super.onDestroy();
        }

        private File arquivo(String nome) {
            File d = getExternalFilesDir(null);
            return d == null ? null : new File(d, nome);
        }

        private void medeTela() {
            try {
                Display d = getDisplayContext() != null ? getDisplayContext().getDisplay() : null;
                if (d != null) d.getRealSize(tela);
            } catch (Throwable t) {
                tela.set(0, 0);
            }
            if (tela.x <= 0 || tela.y <= 0) tela.set(largura, altura);
        }

        /** Superficie do tamanho que a tela inicial pede (nunca menor que a tela). */
        /** Devolve true se pediu um tamanho novo (a superficie vai mudar e redesenhar sozinha). */
        private boolean ajustaTamanho() {
            if (!tamanhoLivre) return false;
            medeTela();
            int w = tela.x + 2 * Math.abs(deslX);
            int h = tela.y + 2 * Math.abs(deslY);
            if (w <= 0 || h <= 0) return false;
            if (w != largura || h != altura) {
                try {
                    getSurfaceHolder().setFixedSize(w, h);
                    return true;
                } catch (Throwable t) {
                    Log.w(TAG, "setFixedSize: " + t);
                    tamanhoLivre = false;
                }
            }
            return false;
        }

        @Override
        public void onDesiredSizeChanged(int w, int h) {
            super.onDesiredSizeChanged(w, h);
            ajustaTamanho();
        }

        private void carrega() {
            File f = arquivo("papel.jpg");
            if (f == null || !f.isFile()) f = arquivo("papel.png");
            if (f == null || !f.isFile()) {
                img = null;
            } else {
                long m = f.lastModified() ^ f.length();
                if (m != lido || img == null) {
                    BitmapFactory.Options o = new BitmapFactory.Options();
                    o.inJustDecodeBounds = true;
                    BitmapFactory.decodeFile(f.getPath(), o);
                    int amostra = 1;
                    while (o.outHeight / amostra > 2400 || o.outWidth / amostra > 5000) amostra *= 2;
                    o = new BitmapFactory.Options();
                    o.inSampleSize = amostra;
                    o.inPreferredConfig = Bitmap.Config.RGB_565;
                    Bitmap novo = BitmapFactory.decodeFile(f.getPath(), o);
                    if (novo != null) {
                        img = novo;
                        int fh = Math.max(1, Math.round(48f * img.getHeight() / img.getWidth()));
                        fundo = Bitmap.createScaledBitmap(img, 48, fh, true);
                        lido = m;
                    }
                }
            }
            paginas = lePaginas();
            leDesloc();
        }

        private int lePaginas() {
            File f = arquivo("paginas.txt");
            if (f == null || !f.isFile()) return 4;
            try (BufferedReader r = new BufferedReader(new FileReader(f))) {
                int p = Integer.parseInt(r.readLine().trim());
                return Math.max(2, Math.min(9, p));
            } catch (Exception e) {
                return 4;
            }
        }

        /** desloc.txt: "X Y", o deslocamento que a tela inicial aplica ao papel (mLastWallpaperDisplayOffset). */
        private void leDesloc() {
            File f = arquivo("desloc.txt");
            if (f == null || !f.isFile()) {
                deslX = 0;
                deslY = 0;
                return;
            }
            long m = f.lastModified() ^ f.length();
            if (m == deslocLido) return;
            deslocLido = m;
            try (BufferedReader r = new BufferedReader(new FileReader(f))) {
                String[] p = r.readLine().trim().split(" +");
                int x = Integer.parseInt(p[0]), y = Integer.parseInt(p[1]);
                if (Math.abs(x) <= 2000 && Math.abs(y) <= 2000) {
                    deslX = x;
                    deslY = y;
                }
            } catch (Exception e) {
                Log.w(TAG, "desloc.txt: " + e);
            }
        }

        /** Canto da parte visivel, em coordenadas da superficie. */
        private float[] visivel() {
            float sobraX = Math.max(0, largura - tela.x), sobraY = Math.max(0, altura - tela.y);
            float vx = sobraX * xOff - deslX, vy = sobraY * yOff - deslY;
            vx = Math.max(0, Math.min(vx, sobraX));
            vy = Math.max(0, Math.min(vy, sobraY));
            return new float[]{vx, vy};
        }

        private float limita(float v) {
            return v < 0f ? 0f : (v > 1f ? 1f : v);
        }

        private void desenha() {
            SurfaceHolder sh = getSurfaceHolder();
            Canvas c = null;
            try {
                c = sh.lockCanvas();
                if (c == null) return;
                c.drawColor(Color.BLACK);
                if (img == null || largura <= 0 || altura <= 0) return;
                medeTela();
                float[] v = visivel();
                float dw = Math.min(tela.x, largura), dh = Math.min(tela.y, altura);
                c.save();
                c.clipRect(v[0], v[1], v[0] + dw, v[1] + dh);
                c.translate(v[0], v[1]);
                float iw = img.getWidth(), ih = img.getHeight();
                if (dw > dh) {
                    // Deitado: imagem inteira, fundo desfocado da propria imagem nas bordas.
                    float sf = Math.max(dw / fundo.getWidth(), dh / fundo.getHeight());
                    mat.setScale(sf, sf);
                    mat.postTranslate((dw - fundo.getWidth() * sf) / 2f, (dh - fundo.getHeight() * sf) / 2f);
                    c.drawBitmap(fundo, mat, escuro);
                    float s = Math.min(dw / iw, dh / ih);
                    mat.setScale(s, s);
                    mat.postTranslate((dw - iw * s) / 2f, (dh - ih * s) / 2f);
                    c.drawBitmap(img, mat, tinta);
                } else {
                    // Em pe: altura cheia, a sobra da largura vira o caminho da rolagem.
                    float s = dh / ih;
                    if (iw * s < dw) s = dw / iw;
                    float sw = iw * s, sh2 = ih * s;
                    mat.setScale(s, s);
                    mat.postTranslate(-(sw - dw) * pos, (dh - sh2) / 2f);
                    c.drawBitmap(img, mat, tinta);
                }
                c.restore();
            } catch (Exception e) {
                // superficie sumiu no meio do desenho: o proximo evento desenha de novo
            } finally {
                if (c != null) {
                    try {
                        sh.unlockCanvasAndPost(c);
                    } catch (Exception ignorado) {
                    }
                }
            }
        }

        @Override
        public void onSurfaceChanged(SurfaceHolder holder, int format, int w, int h) {
            super.onSurfaceChanged(holder, format, w, h);
            largura = w;
            altura = h;
            medeTela();
            Log.i(TAG, "superficie " + w + "x" + h + " tela " + tela.x + "x" + tela.y);
            ajustaTamanho();
            desenha();
        }

        @Override
        public void onSurfaceRedrawNeeded(SurfaceHolder holder) {
            super.onSurfaceRedrawNeeded(holder);
            desenha();
        }

        @Override
        public void onVisibilityChanged(boolean visivel) {
            if (visivel) {
                carrega();
                medeTela();
                if (!ajustaTamanho()) desenha();
            } else {
                animando = false;
                fila.removeCallbacks(this);
            }
        }

        @Override
        public void onOffsetsChanged(float xO, float yO, float xPasso, float yPasso, int xPx, int yPx) {
            xOff = xO;
            yOff = yO;
            // So confia na tela inicial quando ela de fato informa paginas (valor fora do meio).
            if (!lancadorRola && xPasso > 0f && xPasso < 1f && Math.abs(xO - 0.5f) > 0.001f) lancadorRola = true;
            if (lancadorRola) pos = limita(xO);
            desenha();
        }

        @Override
        public void onTouchEvent(MotionEvent e) {
            if (lancadorRola || img == null || tela.x > tela.y) return;
            switch (e.getActionMasked()) {
                case MotionEvent.ACTION_DOWN:
                    x0 = e.getX();
                    y0 = e.getY();
                    pos0 = pos;
                    decidido = false;
                    arrastando = false;
                    animando = false;
                    fila.removeCallbacks(this);
                    if (vel != null) vel.recycle();
                    vel = VelocityTracker.obtain();
                    vel.addMovement(e);
                    break;
                case MotionEvent.ACTION_MOVE: {
                    if (vel != null) vel.addMovement(e);
                    float dx = e.getX() - x0, dy = e.getY() - y0;
                    if (!decidido && (Math.abs(dx) > folga || Math.abs(dy) > folga)) {
                        decidido = true;
                        arrastando = Math.abs(dx) > Math.abs(dy) * 1.2f;
                    }
                    if (arrastando) {
                        pos = limita(pos0 - dx / (tela.x * (float) (paginas - 1)));
                        desenha();
                    }
                    break;
                }
                case MotionEvent.ACTION_UP:
                case MotionEvent.ACTION_CANCEL: {
                    if (arrastando) {
                        float passo = 1f / (paginas - 1);
                        int pag = Math.round(pos / passo);
                        if (vel != null && e.getActionMasked() == MotionEvent.ACTION_UP) {
                            vel.addMovement(e);
                            vel.computeCurrentVelocity(1000);
                            float v = vel.getXVelocity();
                            if (Math.abs(v) > 500f) {
                                int base = Math.round(pos0 / passo);
                                pag = v < 0 ? base + 1 : base - 1;
                            }
                        }
                        anima(limita(pag * passo));
                    }
                    if (vel != null) {
                        vel.recycle();
                        vel = null;
                    }
                    arrastando = false;
                    break;
                }
                default:
                    break;
            }
        }

        private void anima(float alvo) {
            animDe = pos;
            animAlvo = alvo;
            animIni = SystemClock.uptimeMillis();
            animando = true;
            fila.removeCallbacks(this);
            fila.post(this);
        }

        @Override
        public void run() {
            if (!animando) return;
            float t = Math.min(1f, (SystemClock.uptimeMillis() - animIni) / 240f);
            float k = 1f - (1f - t) * (1f - t) * (1f - t);
            pos = animDe + (animAlvo - animDe) * k;
            desenha();
            if (t < 1f) fila.postDelayed(this, 16);
            else animando = false;
        }
    }
}
