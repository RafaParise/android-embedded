package br.embeeded.papel;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.content.pm.ResolveInfo;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.drawable.Drawable;

import java.io.File;
import java.io.FileOutputStream;
import java.io.OutputStreamWriter;
import java.nio.charset.StandardCharsets;
import java.util.List;

/**
 * Desenha o icone de cada app da tela inicial em PNG 192x192, para o PC fazer a versao Matrix (pacote de icones).
 * So le icones e nomes de apps (nada de dado de usuario). Roda pelo adb, que tem a permissao DUMP:
 *   am broadcast -n br.embeeded.papel/.Icones
 * Saida: Android/data/br.embeeded.papel/files/icones/ (PNG + indice.tsv com "pacote/atividade TAB nome").
 */
public class Icones extends BroadcastReceiver {
    @Override
    public void onReceive(Context ctx, Intent intent) {
        final PendingResult fim = goAsync();
        final Context app = ctx.getApplicationContext();
        new Thread(() -> {
            try {
                exporta(app);
            } catch (Exception e) {
                android.util.Log.w("PapelRolante", "icones: " + e);
            } finally {
                fim.finish();
            }
        }).start();
    }

    static void exporta(Context ctx) throws Exception {
        PackageManager pm = ctx.getPackageManager();
        Intent i = new Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER);
        List<ResolveInfo> lista = pm.queryIntentActivities(i, 0);
        File d = new File(ctx.getExternalFilesDir(null), "icones");
        d.mkdirs();
        StringBuilder indice = new StringBuilder();
        for (ResolveInfo r : lista) {
            String comp = r.activityInfo.packageName + "/" + r.activityInfo.name;
            Drawable dr = r.loadIcon(pm);
            Bitmap b = Bitmap.createBitmap(192, 192, Bitmap.Config.ARGB_8888);
            Canvas c = new Canvas(b);
            dr.setBounds(0, 0, 192, 192);
            dr.draw(c);
            String nome = comp.replaceAll("[^A-Za-z0-9._]", "_") + ".png";
            try (FileOutputStream o = new FileOutputStream(new File(d, nome))) {
                b.compress(Bitmap.CompressFormat.PNG, 100, o);
            }
            b.recycle();
            CharSequence rot = r.loadLabel(pm);
            indice.append(comp).append('\t').append(nome).append('\t')
                    .append(rot == null ? "" : rot.toString().replace('\t', ' ').replace('\n', ' ')).append('\n');
        }
        try (OutputStreamWriter w = new OutputStreamWriter(new FileOutputStream(new File(d, "indice.tsv")), StandardCharsets.UTF_8)) {
            w.write(indice.toString());
        }
    }
}
