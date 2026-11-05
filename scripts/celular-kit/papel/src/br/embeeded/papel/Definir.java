package br.embeeded.papel;

import java.lang.reflect.Method;

/**
 * Escolhe o papel de parede animado sem tocar na tela. Roda pelo adb com o usuario shell
 * (que tem SET_WALLPAPER_COMPONENT no A12, conferido em 05/11):
 *   CLASSPATH=$(pm path br.embeeded.papel | cut -d: -f2) app_process / br.embeeded.papel.Definir ativar|desfazer|metodos
 * "desfazer" volta ao papel de parede comum da Samsung (com.android.systemui/.ImageWallpaper).
 */
public class Definir {
    public static void main(String[] a) throws Exception {
        String acao = a.length > 0 ? a[0] : "ativar";
        Object b = Class.forName("android.os.ServiceManager").getMethod("getService", String.class).invoke(null, "wallpaper");
        Object wm = Class.forName("android.app.IWallpaperManager$Stub")
                .getMethod("asInterface", Class.forName("android.os.IBinder")).invoke(null, b);
        if (acao.equals("metodos")) {
            for (Method m : wm.getClass().getMethods()) {
                if (m.getName().startsWith("setWallpaperComponent")) System.out.println(m.toString());
            }
            return;
        }
        if (acao.equals("bloqueio")) {
            // Tira a foto propria da tela de bloqueio: sem ela, o bloqueio mostra o papel da tela inicial
            // (o rolante). A foto original continua na Galeria; voltar = Galeria > Definir como papel > Bloqueio.
            for (Method m : wm.getClass().getMethods()) {
                Class<?>[] p = m.getParameterTypes();
                if (m.getName().equals("clearWallpaper") && p.length == 3 && p[0] == String.class
                        && p[1] == int.class && p[2] == int.class) {
                    m.invoke(wm, "com.android.shell", 2, 0);
                    System.out.println("OK bloqueio");
                    return;
                }
            }
            System.out.println("ERRO: o sistema nao tem clearWallpaper(String,int,int)");
            System.exit(1);
            return;
        }
        android.content.ComponentName cn;
        if (acao.equals("ativar")) {
            cn = new android.content.ComponentName("br.embeeded.papel", "br.embeeded.papel.Papel");
        } else if (acao.equals("desfazer")) {
            cn = new android.content.ComponentName("com.android.systemui", "com.android.systemui.ImageWallpaper");
        } else {
            System.out.println("uso: ativar | desfazer | metodos");
            System.exit(2);
            return;
        }
        Method escolhido = null;
        for (Method m : wm.getClass().getMethods()) {
            if (!m.getName().startsWith("setWallpaperComponent")) continue;
            Class<?>[] p = m.getParameterTypes();
            if (p.length == 0 || p[0] != android.content.ComponentName.class) continue;
            if (escolhido == null || p.length > escolhido.getParameterTypes().length) escolhido = m;
        }
        if (escolhido == null) {
            System.out.println("ERRO: o sistema nao tem setWallpaperComponent");
            System.exit(1);
            return;
        }
        Class<?>[] p = escolhido.getParameterTypes();
        Object[] args = new Object[p.length];
        args[0] = cn;
        int inteiros = 0;
        for (int i = 1; i < p.length; i++) {
            if (p[i] == String.class) {
                args[i] = "com.android.shell";
            } else if (p[i] == int.class) {
                // Android 12: (nome, pacote, usuario). Samsung pode ter (nome, pacote, qual, usuario).
                inteiros++;
                args[i] = 0;
            } else if (p[i] == boolean.class) {
                args[i] = false;
            } else {
                args[i] = null;
            }
        }
        if (inteiros == 2) {
            // qual = FLAG_SYSTEM (1); usuario = 0
            for (int i = 1; i < p.length; i++) {
                if (p[i] == int.class) {
                    args[i] = 1;
                    break;
                }
            }
        }
        escolhido.invoke(wm, args);
        System.out.println("OK " + acao + " via " + escolhido.getName() + "/" + p.length);
    }
}
