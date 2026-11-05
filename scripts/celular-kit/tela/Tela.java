// Escurece a tela do A12 sem o Android saber: camada preta por cima de tudo e brilho temporario 0. O painel, o toque e a depuracao seguem ligados, e nada bloqueia.
// Roda com o usuario shell, por app_process. A camada vive enquanto este processo viver: se ele morrer, a imagem volta sozinha.
// NAO usar SurfaceControl.setDisplayPowerMode: em 04/11 apagar o painel por ele deixou o TOQUE morto depois de acender (o Rafael nao conseguiu desligar um alarme).
// Uso: CLASSPATH=tela.dex app_process / Tela escuro <apertos de volume a devolver> <no do toque> <nos das teclas...>   |   Tela luz volta
// Compilar: scripts/celular-kit/tela/compilar.ps1. Quem chama: scripts/tela-vigia.sh. Motivo e limites: memoria/TELA-APAGADA.md.
import java.io.BufferedReader;
import java.io.FileInputStream;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.lang.reflect.Method;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.concurrent.TimeUnit;

public class Tela {
    static final int EV_KEY = 1;
    static final int EV_ABS = 3;
    static final int ABS_MT_TRACKING_ID = 0x39;
    static final int KEY_VOLUMEUP = 115;
    static final int KEY_POWER = 116;
    static final long IGNORA_NO_INICIO_MS = 800;
    static final long VIGILANCIA_S = 5;
    static final int STREAM_MUSIC = 3;
    static final int WIFI_ALTO_DESEMPENHO = 3;
    static final int ADJUST_LOWER = -1;
    static final int ADJUST_RAISE = 1;
    static final String VIGILANCIA =
        "dumpsys telephony.registry 2>/dev/null | grep mCallState; "
        + "echo alarmes=$(dumpsys audio 2>/dev/null | grep 'AudioPlaybackConfiguration.*state:started' | grep -cE 'USAGE_ALARM|USAGE_NOTIFICATION_RINGTONE'); "
        + "dumpsys power 2>/dev/null | grep -m1 -oE 'mWakefulness=[A-Za-z]+'; "
        + "dumpsys window 2>/dev/null | grep -m1 -oE 'isKeyguardShowing=[a-z]+'";

    /** Guardada aqui porque o coletor de lixo destruiria a camada. */
    static Object camada;
    static final LinkedBlockingQueue<String> FIM = new LinkedBlockingQueue<>();

    /** Dois toques curtos de um dedo so, rapidos ou com ate 2 s entre eles. Toque longo e dois dedos (mao, bolso) zeram a conta. */
    static final class DoisToques {
        static final long TOQUE_MAX_MS = 500;
        static final long INTERVALO_MAX_MS = 2000;
        private int dedos;
        private long inicio;
        private boolean valido;
        private long fimAnterior = -1;

        boolean evento(long ms, int tipo, int codigo, int valor) {
            if (tipo != EV_ABS || codigo != ABS_MT_TRACKING_ID) {
                return false;
            }
            if (valor != -1) {
                if (dedos == 0) {
                    inicio = ms;
                    valido = true;
                } else {
                    valido = false;
                }
                dedos++;
                return false;
            }
            if (dedos == 0) {
                return false;
            }
            dedos--;
            if (dedos > 0) {
                return false;
            }
            if (!valido || ms - inicio > TOQUE_MAX_MS) {
                fimAnterior = -1;
                return false;
            }
            if (fimAnterior >= 0 && inicio - fimAnterior <= INTERVALO_MAX_MS) {
                fimAnterior = -1;
                return true;
            }
            fimAnterior = ms;
            return false;
        }
    }

    /** O que manda acender, lido da saida de VIGILANCIA. Sem dado = nao faz nada. */
    static String motivoDaVigilancia(String saida) {
        String alarme = null;
        String sono = null;
        for (String bruta : saida.split("\n")) {
            String l = bruta.trim();
            if (l.equals("mCallState=1")) {
                return "chamada";
            }
            if (l.startsWith("alarmes=") && !l.equals("alarmes=0") && !l.equals("alarmes=")) {
                alarme = "alarme";
            }
            if (l.startsWith("mWakefulness=") && !l.equals("mWakefulness=Awake")) {
                sono = "dormiu";
            }
            if (l.equals("isKeyguardShowing=true")) {
                sono = "bloqueou";
            }
        }
        return alarme != null ? alarme : sono;
    }

    public static void main(String[] args) throws Exception {
        if (args.length == 2 && args[0].equals("luz")) {
            luz(args[1].equals("volta") ? Float.NaN : Float.parseFloat(args[1]));
            System.out.println("luz " + args[1]);
        } else if (args.length >= 4 && args[0].equals("escuro")) {
            escuro(args);
        } else if (args.length == 1 && args[0].equals("wifi-turbo")) {
            wifiTurbo();
        } else if (args.length == 3 && args[0].equals("wifi")) {
            seguraWifi(Integer.parseInt(args[1]), Long.parseLong(args[2]));
        } else if (args.length == 1 && args[0].equals("mic-solta")) {
            new Mic().solta();
        } else if (args.length == 1 && args[0].equals("testa-mic")) {
            testaMic();
        } else if (args.length == 1 && args[0].equals("mic-olha")) {
            micOlha();
        } else if (args.length == 1 && args[0].equals("testa-toques")) {
            testaToques();
        } else if (args.length == 1 && args[0].equals("testa-vigilancia")) {
            testaVigilancia();
        } else {
            System.err.println("uso: Tela escuro <apertos> <toque> <teclas...> | Tela luz <nivel>|volta");
            System.exit(2);
        }
    }

    static void escuro(String[] args) {
        String motivo = "erro";
        try {
            criaCamada();
            luz(0f);
            leToque("/dev/input/" + args[2]);
            for (int i = 3; i < args.length; i++) {
                leTeclas("/dev/input/" + args[i]);
            }
            devolveVolume(Integer.parseInt(args[1]));
            vigia();
            while (true) {
                atividade();
                String m = FIM.poll(VIGILANCIA_S, TimeUnit.SECONDS);
                if (m != null) {
                    motivo = m;
                    break;
                }
            }
        } catch (Throwable t) {
            motivo = "erro " + t;
        }
        try {
            luz(Float.NaN);
        } catch (Throwable t) {
            motivo += " (brilho nao voltou)";
        }
        if (motivo.equals("volume")) {
            ajustaMidia(ADJUST_LOWER, 1); // o aperto que acendeu tambem subiu a midia
        }
        System.out.println("acendeu: " + motivo);
        System.out.flush();
        System.exit(0);
    }

    static void criaCamada() throws Exception {
        Class<?> sc = Class.forName("android.view.SurfaceControl");
        Class<?> sessao = Class.forName("android.view.SurfaceSession");
        Object b = Class.forName("android.view.SurfaceControl$Builder").getConstructor(sessao).newInstance(sessao.getConstructor().newInstance());
        b.getClass().getMethod("setName", String.class).invoke(b, "tela-preta");
        b.getClass().getMethod("setColorLayer").invoke(b);
        camada = b.getClass().getMethod("build").invoke(b);
        Class<?> tc = Class.forName("android.view.SurfaceControl$Transaction");
        Object t = tc.getConstructor().newInstance();
        tc.getMethod("setLayerStack", sc, int.class).invoke(t, camada, 0);
        tc.getMethod("setLayer", sc, int.class).invoke(t, camada, Integer.MAX_VALUE);
        tc.getMethod("setColor", sc, float[].class).invoke(t, camada, new float[] {0f, 0f, 0f});
        tc.getMethod("setAlpha", sc, float.class).invoke(t, camada, 1f);
        tc.getMethod("show", sc).invoke(t, camada);
        tc.getMethod("apply").invoke(t);
    }

    static Object servico(String nome, String stub) throws Exception {
        Object b = Class.forName("android.os.ServiceManager").getMethod("getService", String.class).invoke(null, nome);
        return Class.forName(stub).getMethod("asInterface", Class.forName("android.os.IBinder")).invoke(null, b);
    }

    /** Brilho temporario do Android: nenhum ajuste salvo muda. NaN devolve o brilho do ajuste. */
    static void luz(float nivel) throws Exception {
        Object dm = servico("display", "android.hardware.display.IDisplayManager$Stub");
        for (Method m : dm.getClass().getMethods()) {
            if (m.getName().equals("setTemporaryBrightness")) {
                if (m.getParameterCount() == 2) {
                    m.invoke(dm, 0, nivel);
                } else {
                    m.invoke(dm, nivel);
                }
                return;
            }
        }
        throw new IllegalStateException("sem setTemporaryBrightness");
    }

    /** O gesto baixou a midia. Em 0 nao devolve: nao da para saber se ja estava em 0, e som do nada e pior que som baixo. */
    static void devolveVolume(int apertos) {
        if (apertos <= 0) {
            return;
        }
        try {
            Object audio = servico("audio", "android.media.IAudioService$Stub");
            for (Method m : audio.getClass().getMethods()) {
                if (m.getName().equals("getStreamVolume") && m.getParameterCount() == 1) {
                    if ((Integer) m.invoke(audio, STREAM_MUSIC) > 0) {
                        ajustaMidia(ADJUST_RAISE, apertos);
                    }
                    return;
                }
            }
        } catch (Throwable t) {
            System.err.println("volume: " + t); // volume errado nao e motivo para acender
        }
    }

    static void ajustaMidia(int direcao, int vezes) {
        try {
            Object audio = servico("audio", "android.media.IAudioService$Stub");
            for (Method m : audio.getClass().getMethods()) {
                if (m.getName().equals("adjustStreamVolume") && m.getParameterCount() == 4) {
                    for (int i = 0; i < vezes; i++) {
                        m.invoke(audio, STREAM_MUSIC, direcao, 0, "com.android.shell");
                    }
                    return;
                }
            }
            System.err.println("sem adjustStreamVolume");
        } catch (Throwable t) {
            System.err.println("volume: " + t);
        }
    }

    /** Conta como uso do aparelho: sem o cabo, e isto que impede o Android de dormir, e dormir bloqueia. */
    static void atividade() throws Exception {
        Object pm = servico("power", "android.os.IPowerManager$Stub");
        long agora = (Long) Class.forName("android.os.SystemClock").getMethod("uptimeMillis").invoke(null);
        for (Method m : pm.getClass().getMethods()) {
            if (m.getName().equals("userActivity")) {
                if (m.getParameterCount() == 4) {
                    m.invoke(pm, 0, agora, 0, 0);
                } else {
                    m.invoke(pm, agora, 0, 0);
                }
                return;
            }
        }
        throw new IllegalStateException("sem userActivity");
    }

    /** Modo do Wi-Fi pedido ao Android enquanto este processo viver: 3 = alto desempenho; 4 = baixa latencia. Ao sair, o Android solta sozinho. */
    static void seguraWifi(int tipo, long segundos) throws Exception {
        Object w = servico("wifi", "android.net.wifi.IWifiManager$Stub");
        Object token = Class.forName("android.os.Binder").getConstructor().newInstance();
        for (Method m : w.getClass().getMethods()) {
            if (m.getName().equals("acquireWifiLock")) {
                Class<?>[] p = m.getParameterTypes();
                Object[] a = new Object[p.length];
                a[0] = token;
                a[1] = tipo;
                a[2] = "tela-wifi";
                Object r = m.invoke(w, a);
                System.out.println("wifi tipo " + tipo + ": " + r);
                Thread.sleep(segundos * 1000L);
                return;
            }
        }
        throw new IllegalStateException("sem acquireWifiLock");
    }

    /** So le e imprime: o que o Android expoe sobre fone, gravacao e microfone. Serve para escolher a deteccao mais barata. */
    static void micOlha() throws Exception {
        Object audio = servico("audio", "android.media.IAudioService$Stub");
        Class<?> sys = Class.forName("android.media.AudioSystem");
        Method estado = sys.getMethod("getDeviceConnectionState", int.class, String.class);
        int[] tipos = {0x80000008, 0x80000010, 0x20, 0x80, 0x80001000};
        for (int t : tipos) {
            System.out.println("disp " + Integer.toHexString(t) + " = " + estado.invoke(null, t, ""));
        }
        System.out.println("modo " + audio.getClass().getMethod("getMode").invoke(audio));
        System.out.println("sco " + audio.getClass().getMethod("isBluetoothScoOn").invoke(audio));
        System.out.println("mudo " + audio.getClass().getMethod("isMicrophoneMuted").invoke(audio));
        java.util.List<?> g = (java.util.List<?>) audio.getClass().getMethod("getActiveRecordingConfigurations").invoke(audio);
        System.out.println("gravando " + g.size());
        for (Object c : g) {
            System.out.println("fonte " + c.getClass().getMethod("getClientAudioSource").invoke(c));
        }
        for (Method m : audio.getClass().getMethods()) {
            if (m.getName().equals("setMicrophoneMute") || m.getName().equals("stopBluetoothSco") || m.getName().equals("setPreferredDevicesForCapturePreset")) {
                System.out.println(m.getName() + " " + java.util.Arrays.toString(m.getParameterTypes()));
            }
        }
    }

    /** auto: canal de voz so enquanto algum app grava. fixo: enquanto o fone estiver conectado. Em chamada (modo != 0) o Android manda. */
    static boolean querSco(String modo, boolean fone, boolean gravando, int modoAudio) {
        if (!fone || modoAudio != 0) {
            return false;
        }
        return modo.equals("fixo") || (modo.equals("auto") && gravando);
    }

    /** Microfone do celular mudo so com o bloqueio pedido, sem fone nenhum e fora de chamada: em toque ou chamada ele volta, sempre. */
    static boolean querMudo(boolean bloqueio, boolean externo, int modoAudio) {
        return bloqueio && !externo && modoAudio == 0;
    }

    /** Fone conta como microfone so com o canal aberto: enquanto ele abre, o app nao pega o chiado do celular. Com o canal desligado por escolha, o fone conta sempre. */
    static boolean foneUtil(boolean fone, boolean canalAberto, String modo) {
        return fone && (canalAberto || modo.equals("desligado"));
    }

    /** Fontes do proprio sistema (palavra de ativacao, referencia de eco) nao contam como gravacao de app. */
    static boolean fonteDeApp(int fonte) {
        return fonte != 1999 && fonte != 1997;
    }

    static void testaMic() throws Exception {
        for (String l : tudo(System.in).split("\n")) {
            String[] c = l.trim().split(" ");
            if (c[0].equals("sco")) {
                System.out.println(querSco(c[1], c[2].equals("1"), c[3].equals("1"), Integer.parseInt(c[4])));
            } else if (c[0].equals("mudo")) {
                System.out.println(querMudo(c[1].equals("1"), c[2].equals("1"), Integer.parseInt(c[3])));
            } else if (c[0].equals("fonte")) {
                System.out.println(fonteDeApp(Integer.parseInt(c[1])));
            } else if (c[0].equals("util")) {
                System.out.println(foneUtil(c[1].equals("1"), c[2].equals("1"), c[3]));
            }
        }
    }

    /** Microfone do fone Bluetooth: reconhece conectar e desconectar sozinho. Morre junto com o processo: o Android fecha o canal. */
    static final class Mic {
        static final int IN_BT = 0x80000008;
        static final int IN_FIO = 0x80000010;
        static final int IN_USB = 0x80001000;
        static final long SEGURA_MS = 3000L;
        static final long CONFERE_MS = 8000L;
        final Object audio;
        final Object token;
        final Method estado;
        final Method inicia;
        final Method para;
        final Method mudo;
        final Method estaMudo;
        final Method modo;
        final Method scoLigado;
        final Method gravacoes;
        boolean aberto;
        boolean abrindo;
        long desde;
        long ultimaGravacao;

        Mic() throws Exception {
            audio = servico("audio", "android.media.IAudioService$Stub");
            token = Class.forName("android.os.Binder").getConstructor().newInstance();
            estado = Class.forName("android.media.AudioSystem").getMethod("getDeviceConnectionState", int.class, String.class);
            Method i = null;
            for (Method m : audio.getClass().getMethods()) {
                if (m.getName().equals("startBluetoothSco") && m.getParameterCount() == 2) {
                    i = m;
                }
            }
            if (i == null) {
                throw new IllegalStateException("sem startBluetoothSco");
            }
            inicia = i;
            Class<?> c = audio.getClass();
            para = c.getMethod("stopBluetoothSco", Class.forName("android.os.IBinder"));
            mudo = c.getMethod("setMicrophoneMute", boolean.class, String.class, int.class);
            estaMudo = c.getMethod("isMicrophoneMuted");
            modo = c.getMethod("getMode");
            scoLigado = c.getMethod("isBluetoothScoOn");
            gravacoes = c.getMethod("getActiveRecordingConfigurations");
        }

        boolean ligado(int tipo) throws Exception {
            return ((Integer) estado.invoke(null, tipo, "")) == 1;
        }

        boolean gravando() throws Exception {
            for (Object g : (java.util.List<?>) gravacoes.invoke(audio)) {
                if (fonteDeApp((Integer) g.getClass().getMethod("getClientAudioSource").invoke(g))) {
                    return true;
                }
            }
            return false;
        }

        void abre(long agora) throws Exception {
            inicia.invoke(audio, token, 29); // 29 = chamada virtual, o que fones comuns aceitam
            aberto = true;
            desde = agora;
        }

        void fecha() throws Exception {
            para.invoke(audio, token);
            aberto = false;
        }

        void passo(String dir) throws Exception {
            long agora = System.currentTimeMillis();
            int m = (Integer) modo.invoke(audio);
            boolean fone = ligado(IN_BT);
            boolean gravaAgora = gravando();
            if (gravaAgora) {
                ultimaGravacao = agora;
            }
            String modoMic = leModo(dir);
            boolean quer = querSco(modoMic, fone, gravaAgora || agora - ultimaGravacao < SEGURA_MS, m);
            if (quer && !aberto) {
                abre(agora);
            } else if (!quer && aberto) {
                fecha();
            } else if (quer && agora - desde > CONFERE_MS && !((Boolean) scoLigado.invoke(audio))) {
                fecha(); // o fone caiu e voltou entre duas voltas: o canal antigo nao serve mais
                abre(agora);
            }
            boolean bloqueio = new java.io.File(dir, "mic-celular.bloqueado").exists();
            boolean canal = (Boolean) scoLigado.invoke(audio);
            abrindo = quer && !canal;
            boolean querMudo = querMudo(bloqueio, foneUtil(fone, canal, modoMic) || ligado(IN_FIO) || ligado(IN_USB), m);
            if (querMudo != (Boolean) estaMudo.invoke(audio)) {
                mudo.invoke(audio, querMudo, "com.android.shell", 0);
            }
        }

        static String leModo(String dir) {
            try (java.io.BufferedReader r = new java.io.BufferedReader(new java.io.FileReader(new java.io.File(dir, "mic-bt.modo")))) {
                String l = r.readLine();
                return l == null ? "auto" : l.trim();
            } catch (java.io.IOException e) {
                return "auto";
            }
        }

        /** Devolve o microfone: quem encerra o processo chama isto, porque o mudo sobrevive a ele. */
        void solta() throws Exception {
            mudo.invoke(audio, false, "com.android.shell", 0);
            System.out.println("microfone do celular liberado");
        }
    }

    /** Wi-Fi em alto desempenho so enquanto a tela estiver em uso; com o aparelho dormindo, solta e a economia volta. Medido em 04/11, com Bluetooth desligado: internet de 54 para 39 ms, oscilacao de 21 para 1,8 ms. */
    static void wifiTurbo() throws Exception {
        Object w = servico("wifi", "android.net.wifi.IWifiManager$Stub");
        Object pm = servico("power", "android.os.IPowerManager$Stub");
        Object token = Class.forName("android.os.Binder").getConstructor().newInstance();
        Method pega = null;
        Method solta = null;
        for (Method m : w.getClass().getMethods()) {
            if (m.getName().equals("acquireWifiLock")) {
                pega = m;
            } else if (m.getName().equals("releaseWifiLock")) {
                solta = m;
            }
        }
        if (pega == null || solta == null) {
            throw new IllegalStateException("sem trava de Wi-Fi");
        }
        Object[] a = new Object[pega.getParameterCount()];
        a[0] = token;
        a[1] = WIFI_ALTO_DESEMPENHO;
        a[2] = "tela-wifi-turbo";
        Method ativo = pm.getClass().getMethod("isInteractive");
        boolean preso = false;
        String dir = System.getenv("TELA_DIR") == null ? "/data/local/tmp" : System.getenv("TELA_DIR");
        Mic mic = null;
        int falhas = 0;
        try {
            mic = new Mic();
        } catch (Exception e) {
            System.err.println("microfone indisponivel: " + e);
        }
        while (true) {
            boolean usando = (Boolean) ativo.invoke(pm);
            if (usando && !preso) {
                pega.invoke(w, a);
                preso = true;
            } else if (!usando && preso) {
                solta.invoke(w, token);
                preso = false;
            }
            if (mic != null && falhas < 5) { // erro no microfone nunca derruba o Wi-Fi
                try {
                    mic.passo(dir);
                    falhas = 0;
                } catch (Exception e) {
                    falhas++;
                    System.err.println("microfone: " + e);
                    if (falhas == 5) {
                        mic.solta();
                    }
                }
            }
            // com o aparelho dormindo este relogio para: nao acorda a CPU. Canal abrindo: confere mais rapido, para soltar o mudo logo
            Thread.sleep(mic != null && mic.abrindo ? 150L : 1000L);
        }
    }

    interface Leitor {
        void evento(long ms, int tipo, int codigo, int valor);
    }

    static void leNo(String caminho, Leitor leitor) throws Exception {
        InputStream in = new FileInputStream(caminho);
        boolean b64 = System.getProperty("os.arch", "").contains("64");
        int tam = b64 ? 24 : 16;
        Thread t = new Thread(() -> {
            byte[] buf = new byte[tam * 64];
            try {
                while (true) {
                    int n = in.read(buf);
                    if (n < tam) {
                        throw new IllegalStateException("leitura curta");
                    }
                    ByteBuffer b = ByteBuffer.wrap(buf, 0, n).order(ByteOrder.LITTLE_ENDIAN);
                    while (b.remaining() >= tam) {
                        long seg = b64 ? b.getLong() : b.getInt();
                        long us = b64 ? b.getLong() : b.getInt();
                        int tipo = b.getShort() & 0xffff;
                        int codigo = b.getShort() & 0xffff;
                        leitor.evento(seg * 1000 + us / 1000, tipo, codigo, b.getInt());
                    }
                }
            } catch (Exception e) {
                FIM.offer("erro lendo " + caminho + ": " + e); // sem o toque ou sem a tecla nao ha como acender: nunca seguir no escuro
            }
        });
        t.setDaemon(true);
        t.start();
    }

    static void leToque(String caminho) throws Exception {
        DoisToques dois = new DoisToques();
        long comeco = System.nanoTime();
        leNo(caminho, (ms, tipo, codigo, valor) -> {
            if (System.nanoTime() - comeco > IGNORA_NO_INICIO_MS * 1000000L && dois.evento(ms, tipo, codigo, valor)) {
                FIM.offer("toques");
            }
        });
    }

    static void leTeclas(String caminho) throws Exception {
        leNo(caminho, (ms, tipo, codigo, valor) -> {
            if (tipo == EV_KEY && codigo == KEY_VOLUMEUP && valor == 1) {
                FIM.offer("volume");
            }
            if (tipo == EV_KEY && codigo == KEY_POWER && valor == 0) {
                FIM.offer("energia"); // na hora de soltar: o Android ja tratou o botao, e quem chamou mostra o PIN
            }
        });
    }

    static void vigia() {
        Thread t = new Thread(() -> {
            while (true) {
                try {
                    Process p = new ProcessBuilder("sh", "-c", VIGILANCIA).start();
                    String m = motivoDaVigilancia(tudo(p.getInputStream()));
                    p.waitFor();
                    if (m != null) {
                        FIM.offer(m);
                    }
                    Thread.sleep(VIGILANCIA_S * 1000L);
                } catch (Exception e) {
                    FIM.offer("erro na vigilancia: " + e); // sem ela um alarme tocaria no escuro
                    return;
                }
            }
        });
        t.setDaemon(true);
        t.start();
    }

    static String tudo(InputStream in) throws Exception {
        StringBuilder s = new StringBuilder();
        try (BufferedReader r = new BufferedReader(new InputStreamReader(in))) {
            for (String l = r.readLine(); l != null; l = r.readLine()) {
                s.append(l).append('\n');
            }
        }
        return s.toString();
    }

    // ---- so para os testes do PC: scripts/tests/test_tela_apagada.py

    static void testaToques() throws Exception {
        DoisToques d = new DoisToques();
        for (String l : tudo(System.in).split("\n")) {
            if (!l.trim().isEmpty()) {
                String[] p = l.trim().split(" ");
                if (d.evento(Long.parseLong(p[0]), Integer.parseInt(p[1]), Integer.parseInt(p[2]), Integer.parseInt(p[3]))) {
                    System.out.println("dispara " + p[0]);
                }
            }
        }
    }

    static void testaVigilancia() throws Exception {
        System.out.println(motivoDaVigilancia(tudo(System.in)));
    }
}
