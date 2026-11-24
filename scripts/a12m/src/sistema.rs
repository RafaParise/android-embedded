//! Leitura do aparelho: /proc, /sys e propriedades. So leitura; nenhuma escrita no Android.

use std::collections::HashMap;
use std::fs;
use std::time::{Duration, Instant};

use crate::leitura;

/// Tamanho da pagina do A12 (arm64 com paginas de 4 KB).
const PAGINA_KB: u64 = 4;
/// Jiffies por segundo no Android (getconf CLK_TCK = 100, conferido no A12 em 20/11).
const CLK_TCK: f64 = 100.0;

pub fn ler(caminho: &str) -> String {
    fs::read_to_string(caminho).unwrap_or_default()
}

/// Um processo numa leitura: nome curto do stat, CPU acumulada, RSS e uid. O cmdline NAO e lido aqui: ler o de
/// outro processo mexe na memoria dele (pagina do zram), entao so os poucos que vao aparecer sao lidos (nomear).
#[derive(Debug, Clone)]
pub struct Proc {
    pub curto: String,
    pub cpu: u64,
    pub rss_kb: u64,
    pub uid: u32,
}

/// Todos os processos visiveis agora (como shell, o grupo readproc ve todos).
pub fn processos() -> HashMap<u32, Proc> {
    let mut m = HashMap::new();
    let Ok(dir) = fs::read_dir("/proc") else { return m };
    for e in dir.flatten() {
        let Some(pid) = e.file_name().to_str().and_then(|s| s.parse::<u32>().ok()) else { continue };
        let base = format!("/proc/{pid}");
        let Some((curto, cpu, rss)) = leitura::processo(&ler(&format!("{base}/stat"))) else { continue };
        m.insert(pid, Proc { curto, cpu, rss_kb: rss * PAGINA_KB, uid: uid_de(&base) });
    }
    m
}

#[cfg(unix)]
fn uid_de(caminho: &str) -> u32 {
    use std::os::unix::fs::MetadataExt;
    fs::metadata(caminho).map(|m| m.uid()).unwrap_or(0)
}

#[cfg(not(unix))]
fn uid_de(_caminho: &str) -> u32 {
    0
}

/// Nome para mostrar de UM processo (le o cmdline so dele).
fn nomear(pid: u32, curto: &str) -> String {
    leitura::nome_exibicao(&fs::read(format!("/proc/{pid}/cmdline")).unwrap_or_default(), curto)
}

/// (nome, % de um nucleo) e (nome, MB).
pub type Maiores = (Vec<(String, f64)>, Vec<(String, u64)>);

/// Os `n` que mais usaram CPU entre duas varreduras (em % de UM nucleo, como o top) e os `n` maiores em RAM.
/// `decorrido` e o tempo REAL entre o inicio das duas varreduras (nao a janela pedida: sob pressao a varredura demora).
pub fn maiores(antes: &HashMap<u32, Proc>, depois: &HashMap<u32, Proc>, decorrido: Duration, n: usize) -> Maiores {
    let jiffies = (decorrido.as_secs_f64() * CLK_TCK).max(1.0);
    let mut cpu: Vec<(u32, f64)> = depois
        .iter()
        .filter_map(|(pid, p)| {
            let a = antes.get(pid)?;
            let d = p.cpu.saturating_sub(a.cpu);
            (d > 0).then(|| (*pid, (d as f64 * 1000.0 / jiffies).round() / 10.0))
        })
        .collect();
    cpu.sort_by(|a, b| b.1.total_cmp(&a.1));
    cpu.truncate(n);
    let mut ram: Vec<(u32, u64)> = depois.iter().map(|(pid, p)| (*pid, p.rss_kb / 1024)).collect();
    ram.sort_by_key(|x| std::cmp::Reverse(x.1));
    ram.truncate(n);
    let nome = |pid: &u32| depois.get(pid).map(|p| nomear(*pid, &p.curto)).unwrap_or_default();
    (
        cpu.iter().map(|(pid, v)| (nome(pid), *v)).collect(),
        ram.iter().map(|(pid, v)| (nome(pid), *v)).collect(),
    )
}

/// Propriedade do sistema pela libc da bionic (sem disparar `getprop`).
#[cfg(target_os = "android")]
pub fn prop(nome: &str) -> String {
    use std::ffi::{c_char, c_int, CString};
    extern "C" {
        fn __system_property_get(nome: *const c_char, valor: *mut c_char) -> c_int;
    }
    let Ok(c) = CString::new(nome) else { return String::new() };
    let mut buf = [0u8; 92]; // PROP_VALUE_MAX
    // SAFETY: buf tem PROP_VALUE_MAX bytes, o tamanho maximo que a bionic escreve, e c termina em NUL.
    let n = unsafe { __system_property_get(c.as_ptr(), buf.as_mut_ptr().cast()) };
    String::from_utf8_lossy(&buf[..usize::try_from(n).unwrap_or(0).min(buf.len())]).into_owned()
}

#[cfg(not(target_os = "android"))]
pub fn prop(_nome: &str) -> String {
    String::new()
}

/// Temperaturas pelo `dumpsys thermalservice` (~40 ms no A12; /sys/class/thermal e power_supply sao fechados ao shell).
#[cfg(target_os = "android")]
pub fn temperaturas() -> Vec<(String, f64)> {
    use std::process::{Command, Stdio};
    Command::new("/system/bin/dumpsys")
        .arg("thermalservice")
        .stdin(Stdio::null())
        .stderr(Stdio::null())
        .output()
        .map(|o| leitura::temperaturas(&String::from_utf8_lossy(&o.stdout)))
        .unwrap_or_default()
}

#[cfg(not(target_os = "android"))]
pub fn temperaturas() -> Vec<(String, f64)> {
    Vec::new()
}

/// Objeto JSON {"AP":36.4,"BAT":34.2} (nomes ja filtrados: so letras, digitos e _).
pub fn temps_json(v: &[(String, f64)]) -> String {
    let itens: Vec<String> = v.iter().map(|(n, c)| format!("{}:{c}", js(n))).collect();
    format!("{{{}}}", itens.join(","))
}

/// Lista JSON de textos.
pub fn textos_json(v: &[String]) -> String {
    let itens: Vec<String> = v.iter().map(|x| js(x)).collect();
    format!("[{}]", itens.join(","))
}

/// Uma foto do aparelho.
pub struct Foto {
    pub janela_s: u64,
    pub mem: leitura::Memoria,
    pub zram: (u64, u64),
    pub psi_cpu: leitura::Pressao,
    pub psi_mem: (leitura::Pressao, leitura::Pressao),
    pub psi_io: (leitura::Pressao, leitura::Pressao),
    pub cpu_pct: f64,
    pub total: usize,
    pub apps: usize,
    pub top_cpu: Vec<(String, f64)>,
    pub top_ram: Vec<(String, u64)>,
    pub temps: Vec<(String, f64)>,
    pub tuneis: Vec<String>,
}

pub fn foto(janela: Duration) -> Foto {
    // a janela de /proc/stat fica ENTRE as varreduras: a CPU da propria varredura nao entra no total medido
    let t0 = Instant::now();
    let p0 = processos();
    let c0 = leitura::cpu_total(&ler("/proc/stat"));
    std::thread::sleep(janela);
    let c1 = leitura::cpu_total(&ler("/proc/stat"));
    let t1 = Instant::now();
    let mut p1 = processos();
    // como o "ps -A | wc -l" do medir.py: conta o proprio processo e o sh do adb, mais a linha de cabecalho
    let total = p1.len() + 1;
    let apps = p1.values().filter(|p| leitura::eh_app(p.uid)).count();
    // o proprio a12m nao entra entre os maiores: mediria a si mesmo
    p1.remove(&std::process::id());
    let cpu_pct = match (c0, c1) {
        (Some(a), Some(b)) => leitura::cpu_ocupada_pct(a, b),
        _ => 0.0,
    };
    let (top_cpu, top_ram) = maiores(&p0, &p1, t1 - t0, 5);
    Foto {
        janela_s: janela.as_secs(),
        mem: leitura::memoria(&ler("/proc/meminfo")),
        zram: leitura::zram(&ler("/sys/block/zram0/mm_stat")),
        psi_cpu: leitura::pressao(&ler("/proc/pressure/cpu")).0,
        psi_mem: leitura::pressao(&ler("/proc/pressure/memory")),
        psi_io: leitura::pressao(&ler("/proc/pressure/io")),
        cpu_pct,
        total,
        apps,
        top_cpu,
        top_ram,
        temps: temperaturas(),
        tuneis: leitura::tuneis(&ler("/proc/net/dev")),
    }
}

/// Texto JSON com aspas e escapes (sem depender de serde).
pub fn js(s: &str) -> String {
    let mut o = String::with_capacity(s.len() + 2);
    o.push('"');
    for c in s.chars() {
        match c {
            '"' => o.push_str("\\\""),
            '\\' => o.push_str("\\\\"),
            '\n' => o.push_str("\\n"),
            c if (c as u32) < 0x20 => o.push_str(&format!("\\u{:04x}", c as u32)),
            c => o.push(c),
        }
    }
    o.push('"');
    o
}

/// Lista JSON de objetos {chave_nome: nome, chave_valor: valor}.
pub fn lista_json<T: std::fmt::Display>(v: &[(String, T)], chave_valor: &str) -> String {
    let itens: Vec<String> = v.iter().map(|(n, x)| format!("{{\"nome\":{},\"{chave_valor}\":{x}}}", js(n))).collect();
    format!("[{}]", itens.join(","))
}

impl Foto {
    /// JSON com a MESMA estrutura do medir.py (rotulo, quando, mem, proc, psi, cpu.maiores): o
    /// `medir.py --comparar` funciona entre os dois. proc.servicos e mem.em_cache_mb nao existem aqui.
    pub fn json(&self, quando: &str, rotulo: &str) -> String {
        let m = &self.mem;
        let p = |x: &leitura::Pressao| (x.avg10, x.avg60);
        let (c10, c60) = p(&self.psi_cpu);
        let (ms10, ms60) = p(&self.psi_mem.0);
        let (mf10, mf60) = p(&self.psi_mem.1);
        let (is10, is60) = p(&self.psi_io.0);
        let (if10, if60) = p(&self.psi_io.1);
        format!(
            concat!(
                "{{\"rotulo\":{},\"quando\":{},\"fonte\":\"a12m\",",
                "\"mem\":{{\"disponivel_mb\":{},\"livre_mb\":{},\"total_mb\":{},\"swap_usado_mb\":{},\"zram_dados_mb\":{},\"zram_comprimido_mb\":{}}},",
                "\"proc\":{{\"total\":{},\"apps\":{}}},",
                "\"psi\":{{\"cpu_some_avg10\":{},\"cpu_some_avg60\":{},\"mem_some_avg10\":{},\"mem_some_avg60\":{},",
                "\"mem_full_avg10\":{},\"mem_full_avg60\":{},\"io_some_avg10\":{},\"io_some_avg60\":{},\"io_full_avg10\":{},\"io_full_avg60\":{}}},",
                "\"cpu\":{{\"ocupada_pct\":{},\"janela_s\":{},\"maiores\":{}}},",
                "\"maiores_ram\":{},\"temperatura_c\":{},\"tuneis\":{}}}"
            ),
            js(rotulo), js(quando),
            m.disponivel_mb, m.livre_mb, m.total_mb, m.swap_usado_mb(), self.zram.0, self.zram.1,
            self.total, self.apps,
            c10, c60, ms10, ms60, mf10, mf60, is10, is60, if10, if60,
            self.cpu_pct, self.janela_s, lista_json(&self.top_cpu, "cpu_pct"),
            lista_json(&self.top_ram, "mb"),
            temps_json(&self.temps),
            textos_json(&self.tuneis),
        )
    }

    /// Resumo de poucas linhas para a tela (mesmo formato de leitura do medir.py).
    pub fn texto(&self) -> String {
        let m = &self.mem;
        let cpu: Vec<String> = self.top_cpu.iter().map(|(n, p)| format!("{n} {p}%")).collect();
        let ram: Vec<String> = self.top_ram.iter().map(|(n, mb)| format!("{n} {mb} MB")).collect();
        let temps: Vec<String> = self.temps.iter().map(|(n, c)| format!("{n} {c:.1} C")).collect();
        format!(
            "memoria: disponivel {} MB | livre {} MB | swap usado {} MB | zram {} MB -> {} MB\n\
             pressao (avg60): cpu {}% | memoria {}% | disco {}%\n\
             CPU ocupada ({} s): {}% | processos: {} total, {} de apps\n\
             temperatura: {} | tuneis (VPN): {}\n\
             maiores CPU: {}\nmaiores RAM: {}",
            m.disponivel_mb, m.livre_mb, m.swap_usado_mb(), self.zram.0, self.zram.1,
            self.psi_cpu.avg60, self.psi_mem.0.avg60, self.psi_io.0.avg60,
            self.janela_s, self.cpu_pct, self.total, self.apps,
            if temps.is_empty() { "sem leitura".into() } else { temps.join(" | ") },
            if self.tuneis.is_empty() { "nenhum".into() } else { self.tuneis.join(", ") },
            if cpu.is_empty() { "-".into() } else { cpu.join("; ") },
            ram.join("; ")
        )
    }
}

/// Sinais do que o sistema permite (so leitura): freezer, lmkd e RAM Plus.
pub fn conferir() -> Vec<(String, String)> {
    let mut v = vec![
        ("freezer v2 (cgroup.freeze do uid_0)".to_string(), ler("/sys/fs/cgroup/uid_0/cgroup.freeze").trim().to_string()),
        ("freezer v1 (/dev/freezer/frozen)".to_string(), ler("/dev/freezer/frozen/freezer.state").trim().to_string()),
    ];
    for p in [
        "ro.lmk.psi_complete_stall_ms",
        "ro.lmk.swap_free_low_percentage",
        "ro.lmk.downgrade_pressure",
        "ro.config.low_ram",
        "persist.sys.zram.ram_expand_size",
    ] {
        v.push((p.to_string(), prop(p)));
    }
    v
}

#[cfg(test)]
mod testes {
    use super::*;

    fn p(curto: &str, cpu: u64, rss_kb: u64) -> Proc {
        Proc { curto: curto.into(), cpu, rss_kb, uid: 10_100 }
    }

    #[test]
    fn maiores_por_cpu_e_ram_no_tempo_real() {
        // pids altos e ficticios: no PC nao ha /proc, entao o nome vem do stat (filtrado)
        let a: HashMap<u32, Proc> =
            [(900_001, p("a", 100, 10_240)), (900_002, p("b", 50, 204_800)), (900_003, p("c", 0, 1024))].into();
        let d: HashMap<u32, Proc> = [
            (900_001, p("a", 300, 10_240)),
            (900_002, p("b", 60, 204_800)),
            (900_003, p("c", 0, 1024)),
            (900_004, p("novo", 999, 2048)),
        ]
        .into();
        let (cpu, ram) = maiores(&a, &d, Duration::from_secs(2), 2);
        assert_eq!(cpu, vec![("a".into(), 100.0), ("b".into(), 5.0)], "novo no meio da janela nao entra");
        assert_eq!(ram, vec![("b".into(), 200), ("a".into(), 10)]);
        // a varredura demorou: 4 s reais em vez de 2 -> metade do percentual
        let (cpu, _) = maiores(&a, &d, Duration::from_secs(4), 1);
        assert_eq!(cpu, vec![("a".into(), 50.0)]);
    }

    #[test]
    fn json_escapa_texto_e_tem_a_estrutura_do_medir() {
        assert_eq!(js("a\"b\\c\n\u{1}"), "\"a\\\"b\\\\c\\n\\u0001\"");
        assert_eq!(lista_json(&[("x".to_string(), 1.5)], "cpu_pct"), "[{\"nome\":\"x\",\"cpu_pct\":1.5}]");
        assert_eq!(temps_json(&[("AP".to_string(), 36.4), ("BAT".to_string(), 34.0)]), "{\"AP\":36.4,\"BAT\":34}");
        assert_eq!(temps_json(&[]), "{}");
        assert_eq!(textos_json(&["tun0".to_string()]), "[\"tun0\"]");
        assert_eq!(textos_json(&[]), "[]");
    }
}
