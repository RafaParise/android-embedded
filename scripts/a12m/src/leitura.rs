//! Leitores puros dos arquivos do kernel (texto -> numeros). Sem acesso a disco: os testes usam texto ficticio.

/// Linhas de /proc/meminfo em MB (o kernel escreve em kB).
#[derive(Debug, Default, Clone, Copy, PartialEq)]
pub struct Memoria {
    pub total_mb: u64,
    pub disponivel_mb: u64,
    pub livre_mb: u64,
    pub swap_total_mb: u64,
    pub swap_livre_mb: u64,
}

impl Memoria {
    pub fn swap_usado_mb(&self) -> u64 {
        self.swap_total_mb.saturating_sub(self.swap_livre_mb)
    }
}

pub fn memoria(meminfo: &str) -> Memoria {
    let mut m = Memoria::default();
    for linha in meminfo.lines() {
        let mut partes = linha.split_whitespace();
        let (Some(chave), Some(valor)) = (partes.next(), partes.next()) else { continue };
        let Ok(kb) = valor.parse::<u64>() else { continue };
        let mb = kb / 1024;
        match chave {
            "MemTotal:" => m.total_mb = mb,
            "MemAvailable:" => m.disponivel_mb = mb,
            "MemFree:" => m.livre_mb = mb,
            "SwapTotal:" => m.swap_total_mb = mb,
            "SwapFree:" => m.swap_livre_mb = mb,
            _ => {}
        }
    }
    m
}

/// /sys/block/zram0/mm_stat: 1o campo = dados originais, 2o = comprimidos (bytes).
pub fn zram(mm_stat: &str) -> (u64, u64) {
    let mut c = mm_stat.split_whitespace().map(|v| v.parse::<u64>().unwrap_or(0));
    let orig = c.next().unwrap_or(0);
    let comp = c.next().unwrap_or(0);
    (orig / (1024 * 1024), comp / (1024 * 1024))
}

/// Uma linha "some"/"full" de /proc/pressure/*: medias moveis (%) e o total acumulado de espera (microssegundos).
#[derive(Debug, Default, Clone, Copy, PartialEq)]
pub struct Pressao {
    pub avg10: f64,
    pub avg60: f64,
    pub total_us: u64,
}

/// (some, full) de um arquivo de /proc/pressure. O de cpu no 4.19 so tem "some".
pub fn pressao(texto: &str) -> (Pressao, Pressao) {
    let mut some = Pressao::default();
    let mut full = Pressao::default();
    for linha in texto.lines() {
        let alvo = if linha.starts_with("some") {
            &mut some
        } else if linha.starts_with("full") {
            &mut full
        } else {
            continue;
        };
        for campo in linha.split_whitespace() {
            if let Some(v) = campo.strip_prefix("avg10=") {
                alvo.avg10 = v.parse().unwrap_or(0.0);
            } else if let Some(v) = campo.strip_prefix("avg60=") {
                alvo.avg60 = v.parse().unwrap_or(0.0);
            } else if let Some(v) = campo.strip_prefix("total=") {
                alvo.total_us = v.parse().unwrap_or(0);
            }
        }
    }
    (some, full)
}

/// Percentual do intervalo em que houve espera, pela diferenca do total acumulado (pega pico CURTO entre duas
/// leituras, que a media avg10 lida a cada 30 s deixa passar).
pub fn espera_pct(total_antes_us: u64, total_depois_us: u64, intervalo_us: u64) -> f64 {
    if intervalo_us == 0 {
        return 0.0;
    }
    let d = total_depois_us.saturating_sub(total_antes_us) as f64;
    ((d * 1000.0 / intervalo_us as f64).round() / 10.0).min(100.0)
}

/// Linha "cpu " de /proc/stat: (ocupado, total) em jiffies. Ocioso = idle + iowait.
pub fn cpu_total(stat: &str) -> Option<(u64, u64)> {
    let linha = stat.lines().find(|l| l.starts_with("cpu "))?;
    let v: Vec<u64> = linha.split_whitespace().skip(1).map(|x| x.parse().unwrap_or(0)).collect();
    if v.len() < 5 {
        return None;
    }
    let total: u64 = v.iter().sum();
    let ocioso = v[3] + v[4];
    Some((total - ocioso, total))
}

/// Percentual ocupado entre duas leituras de `cpu_total`.
pub fn cpu_ocupada_pct(antes: (u64, u64), depois: (u64, u64)) -> f64 {
    let ocup = depois.0.saturating_sub(antes.0) as f64;
    let total = depois.1.saturating_sub(antes.1) as f64;
    if total <= 0.0 {
        0.0
    } else {
        (ocup * 1000.0 / total).round() / 10.0
    }
}

/// /proc/<pid>/stat: (nome curto, utime+stime em jiffies, rss em paginas). O nome fica entre parenteses e pode ter
/// espaco ou parentese dentro: o fim do nome e o ULTIMO ")".
pub fn processo(stat: &str) -> Option<(String, u64, u64)> {
    let ini = stat.find('(')?;
    let fim = stat.rfind(')')?;
    let nome = stat.get(ini + 1..fim)?.to_string();
    let resto: Vec<&str> = stat.get(fim + 1..)?.split_whitespace().collect();
    // depois do nome: estado(0) ppid(1) ... utime(11) stime(12) ... starttime(19) vsize(20) rss(21)
    let utime: u64 = resto.get(11)?.parse().ok()?;
    let stime: u64 = resto.get(12)?.parse().ok()?;
    let rss: u64 = resto.get(21)?.parse().ok()?;
    Some((nome, utime + stime, rss))
}

/// starttime do /proc/<pid>/stat (jiffies desde o boot), campo 22 do kernel = indice 19 depois do nome.
pub fn inicio_processo(stat: &str) -> Option<u64> {
    let fim = stat.rfind(')')?;
    stat.get(fim + 1..)?.split_whitespace().nth(19)?.parse().ok()
}

/// Nome so com ASCII alfanumerico e "._:-", ate 80 caracteres (pacote ou programa; nada de texto livre).
fn nome_limpo(s: &str) -> bool {
    // "@" e "+" aparecem em servicos do sistema (android.hardware.graphics.composer@2.1-service); espaco nunca passa
    !s.is_empty() && s.len() <= 80 && s.chars().all(|c| c.is_ascii_alphanumeric() || "._:-/@+".contains(c))
}

/// Nome curto do stat (comm, ate 15 bytes, pode vir de prctl com texto qualquer): so passa se for limpo.
pub fn nome_curto_seguro(curto: &str) -> String {
    if nome_limpo(curto) { curto.to_string() } else { "(nome oculto)".to_string() }
}

/// Nome para mostrar a partir de /proc/<pid>/cmdline: so o 1o argumento sem o caminho, e so se for limpo (sem
/// argumentos, que podem ter dado pessoal). Senao, o nome curto, tambem filtrado.
pub fn nome_exibicao(cmdline: &[u8], nome_curto: &str) -> String {
    let primeiro = cmdline.split(|b| *b == 0).next().unwrap_or(&[]);
    let texto = String::from_utf8_lossy(primeiro);
    let base = texto.rsplit('/').next().unwrap_or("");
    if nome_limpo(base) && !base.contains('/') { base.to_string() } else { nome_curto_seguro(nome_curto) }
}

/// Processo de app como o medir.py conta (USER u0_aNN e u0_aiNN): uid 10000-19999 ou 90000-98999 do usuario 0.
pub fn eh_app(uid: u32) -> bool {
    (10_000..=19_999).contains(&uid) || (90_000..=98_999).contains(&uid)
}

/// Data e hora em Brasilia (UTC-3, sem horario de verao desde 2019) a partir de segundos Unix, em ISO.
pub fn iso_brasilia(segundos_unix: u64) -> String {
    let s = segundos_unix as i64 - 3 * 3600;
    let dias = s.div_euclid(86_400);
    let resto = s.rem_euclid(86_400);
    // dias civis (Howard Hinnant)
    let z = dias + 719_468;
    let era = z.div_euclid(146_097);
    let doe = z - era * 146_097;
    let yoe = (doe - doe / 1460 + doe / 36_524 - doe / 146_096) / 365;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = doy - (153 * mp + 2) / 5 + 1;
    let m = if mp < 10 { mp + 3 } else { mp - 9 };
    let a = yoe + era * 400 + i64::from(m <= 2);
    format!("{a:04}-{m:02}-{d:02}T{:02}:{:02}:{:02}-03:00", resto / 3600, resto % 3600 / 60, resto % 60)
}

/// Temperaturas do `dumpsys thermalservice` como (nome, graus C), uma por nome, na ordem em que aparecem, so de 1 a 120 C
/// (o A12 lista SUBBAT com 0.0). Prefere a secao "Current temperatures from HAL" (leitura nova); sem ela, usa o que houver.
/// So linhas `Temperature{...}`: as de `CoolingDevice{...}` tambem tem mValue e mName. O kernel (/sys/class/thermal e
/// power_supply) e fechado para o shell neste A12 (conferido em 24/11).
pub fn temperaturas(texto: &str) -> Vec<(String, f64)> {
    let parte = texto.find("Current temperatures from HAL").map_or(texto, |i| &texto[i..]);
    let mut v: Vec<(String, f64)> = Vec::new();
    for linha in parte.lines().filter(|l| l.contains("Temperature{")) {
        let (Some(i), Some(j)) = (linha.find("mValue="), linha.find("mName=")) else { continue };
        let valor: Option<f64> = linha[i + 7..].split(',').next().and_then(|x| x.trim().parse().ok());
        let nome = linha[j + 6..].split([',', '}']).next().unwrap_or("").trim();
        let nome_ok = !nome.is_empty() && nome.bytes().all(|b| b.is_ascii_alphanumeric() || b == b'_');
        if let Some(c) = valor {
            if (1.0..=120.0).contains(&c) && nome_ok && !v.iter().any(|(n, _)| n == nome) {
                v.push((nome.to_string(), c));
            }
        }
    }
    v
}

/// Graus da temperatura `nome` na lista (0.0 se nao houver).
pub fn grau(v: &[(String, f64)], nome: &str) -> f64 {
    v.iter().find(|(n, _)| n == nome).map_or(0.0, |(_, c)| *c)
}

/// Tuneis de VPN de pe em /proc/net/dev (tun0 = Tailscale ou FortiClient; wg, ppp), em ordem. tunl0, sit0, ip6tnl0 e
/// ip_vti0 sao do kernel e ficam sempre na lista: por isso o nome tem de ser prefixo + so digitos.
pub fn tuneis(net_dev: &str) -> Vec<String> {
    let mut v: Vec<String> = net_dev
        .lines()
        .filter_map(|l| l.split_once(':'))
        .map(|(n, _)| n.trim().to_string())
        .filter(|n| {
            ["tun", "wg", "ppp"].iter().any(|p| {
                n.strip_prefix(p).is_some_and(|r| !r.is_empty() && r.bytes().all(|b| b.is_ascii_digit()))
            })
        })
        .collect();
    v.sort();
    v
}

#[cfg(test)]
mod testes {
    use super::*;

    #[test]
    fn temperaturas_do_thermalservice() {
        let t = "Thermal Status: 0\nCached temperatures:\n\tTemperature{mValue=99.0, mType=0, mName=AP, mStatus=0}\n\
                 HAL Ready: true\nCurrent temperatures from HAL:\n\tTemperature{mValue=0.0, mType=2, mName=SUBBAT, mStatus=0}\n\
                 \tTemperature{mValue=36.4, mType=0, mName=AP, mStatus=0}\n\tTemperature{mValue=34.2, mType=2, mName=BAT, mStatus=0}\n\
                 \tTemperature{mValue=37.0, mType=0, mName=AP, mStatus=0}\nCurrent cooling devices from HAL:\n\
                 \tCoolingDevice{mValue=3, mType=2, mName=battery}\n";
        let v = temperaturas(t);
        assert_eq!(v, vec![("AP".to_string(), 36.4), ("BAT".to_string(), 34.2)], "secao nova, uma por nome, sem SUBBAT nem cooling");
        assert_eq!(grau(&v, "BAT"), 34.2);
        assert_eq!(grau(&v, "PA"), 0.0);
        let so_cache = "Temperature{mValue=40.5, mType=0, mName=AP, mStatus=0}";
        assert_eq!(temperaturas(so_cache), vec![("AP".to_string(), 40.5)], "sem a secao nova: usa o que houver");
        assert!(temperaturas("Temperature{mValue=41.0, mType=0, mName=Jo ao, mStatus=0}").is_empty(), "nome estranho fica fora");
        assert!(temperaturas("").is_empty());
    }

    #[test]
    fn tuneis_de_vpn_sem_os_do_kernel() {
        let t = "Inter-|   Receive\n face |bytes    packets\n  tunl0: 0 0\n    lo: 1 2\n  tun0: 5 6\nip6tnl0: 0\n\
                 ip_vti0: 0\n wlan0: 9\n  sit0: 0\n   wg1: 3\n  ppp0: 1\n  tunx: 1\n   tun: 2\n";
        assert_eq!(tuneis(t), vec!["ppp0", "tun0", "wg1"]);
        assert!(tuneis("").is_empty());
    }

    #[test]
    fn le_meminfo_em_mb() {
        let t = "MemTotal:        3841188 kB\nMemFree:          704512 kB\nMemAvailable:    1974272 kB\n\
                 SwapTotal:       4194300 kB\nSwapFree:        2977792 kB\nlixo\n";
        let m = memoria(t);
        assert_eq!((m.total_mb, m.livre_mb, m.disponivel_mb), (3751, 688, 1928));
        assert_eq!(m.swap_usado_mb(), 4095 - 2908);
    }

    #[test]
    fn le_zram_e_pressao_com_total() {
        assert_eq!(zram("1039138816 205520896 220000000 0 0 0 0 0 0"), (991, 196));
        assert_eq!(zram(""), (0, 0));
        let (s, f) = pressao("some avg10=1.35 avg60=0.32 avg300=0.30 total=716829168\nfull avg10=0.96 avg60=0.22 avg300=0.17 total=413064140\n");
        assert_eq!((s.avg10, s.avg60, s.total_us, f.avg10, f.total_us), (1.35, 0.32, 716_829_168, 0.96, 413_064_140));
        let (s, f) = pressao("some avg10=12.00 avg60=3.50 avg300=1.00 total=9\n");
        assert_eq!((s.avg10, f.avg10), (12.0, 0.0), "cpu no 4.19 so tem some");
    }

    #[test]
    fn espera_curta_entre_leituras_aparece() {
        // 3 s de espera de memoria dentro de um intervalo de 30 s = 10% (a avg10 lida no fim ja teria caido)
        assert_eq!(espera_pct(1_000_000, 4_000_000, 30_000_000), 10.0);
        assert_eq!(espera_pct(5, 5, 30_000_000), 0.0);
        assert_eq!(espera_pct(9, 5, 30_000_000), 0.0, "contador reiniciado nao vira negativo");
        assert_eq!(espera_pct(0, 99, 0), 0.0);
        assert_eq!(espera_pct(0, 60_000_000, 30_000_000), 100.0, "teto");
    }

    #[test]
    fn cpu_entre_duas_leituras() {
        let a = cpu_total("cpu  100 0 100 700 100 0 0 0 0 0\ncpu0 1 2 3 4 5\n").unwrap();
        let d = cpu_total("cpu  130 0 110 760 100 0 0 0 0 0\n").unwrap();
        assert_eq!(a, (200, 1000));
        assert_eq!(cpu_ocupada_pct(a, d), 40.0);
        assert_eq!(cpu_ocupada_pct(a, a), 0.0);
        assert!(cpu_total("intr 1 2 3").is_none());
    }

    #[test]
    fn stat_de_processo_com_nome_estranho() {
        let t = "30848 (stagram.android) S 648 648 0 0 -1 1077952832 141157 2 0 0 500 120 0 0 20 0 80 0 1234 900000000 45165 x";
        assert_eq!(processo(t), Some(("stagram.android".into(), 620, 45165)));
        assert_eq!(inicio_processo(t), Some(1234));
        let t = "12 (a (b) c) R 1 1 0 0 -1 0 0 0 0 0 7 3 0 0 20 0 1 0 1 1 9 x";
        assert_eq!(processo(t), Some(("a (b) c".into(), 10, 9)));
        assert_eq!(processo("lixo"), None);
    }

    #[test]
    fn nome_sem_caminho_argumento_nem_texto_livre() {
        assert_eq!(nome_exibicao(b"com.whatsapp.w4b\0", "w4b"), "com.whatsapp.w4b");
        assert_eq!(nome_exibicao(b"/system/bin/surfaceflinger\0", "surfaceflinger"), "surfaceflinger");
        assert_eq!(nome_exibicao(b"python\0/home/x/arquivo do aluno.py\0", "python"), "python");
        assert_eq!(nome_exibicao(b"bash meu nome\0", "bash"), "bash", "com espaco: usa o nome curto");
        assert_eq!(nome_exibicao(b"", "kworker/0:1"), "kworker/0:1");
        assert_eq!(nome_exibicao(b"", "Maria Silva"), "(nome oculto)", "comm com texto livre nao aparece");
        assert_eq!(
            nome_exibicao(b"/vendor/bin/hw/android.hardware.graphics.composer@2.1-service ", "composer@2.1-se"),
            "android.hardware.graphics.composer@2.1-service"
        );
        assert_eq!(nome_exibicao(b"Jo\xc3\xa3o\0", "Jo\u{e3}o"), "(nome oculto)");
    }

    #[test]
    fn conta_app_como_o_medir() {
        assert!(eh_app(10_954) && eh_app(90_001));
        assert!(!eh_app(1000) && !eh_app(99_123) && !eh_app(1_010_001), "isolado u0_i e outro usuario ficam fora");
    }

    #[test]
    fn hora_de_brasilia() {
        assert_eq!(iso_brasilia(1_794_762_298), "2026-11-15T14:04:58-03:00");
        assert_eq!(iso_brasilia(0), "1969-12-31T21:00:00-03:00");
    }
}
