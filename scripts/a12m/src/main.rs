//! a12m - sensor nativo do Galaxy A12 (Android Embeeded, 20/11/2026).
//!
//! Versao adaptada e honesta do "a12-engine" que o Gemini propos (DECISOES.md, 20/11): SO LE. Nao muda ajuste, nao mata
//! app, nao mexe em bucket, DNS, Wi-Fi nem opcoes do desenvolvedor (os ajustes ficam no ajustes-script.py, com desfazer).
//! Roda como shell (adb do PC ou adb loopback do Termux), que le /proc/stat e /proc de todos os processos; o Termux nao le.
//!
//!   a12m status [--json] [--janela S] [--rotulo R]   foto do aparelho numa chamada (JSON na estrutura do medir.py)
//!   a12m vigiar [--intervalo S]                      residente (15 s): episodios de pressao e quem causou, calor (AP e
//!                                                    bateria), memoria livre baixa e tuneis da VPN que caem ou voltam
//!   a12m episodios [N]                               os ultimos N registros
//!   a12m custo                                       quanto o proprio vigia gasta (RSS e CPU media desde que subiu)
//!   a12m parar                                       para o vigia
//!   a12m conferir                                    o que o sistema permite (freezer, lmkd, RAM Plus)

mod leitura;
mod sistema;

use std::fs::{self, File, OpenOptions};
use std::io::Write;
use std::path::{Path, PathBuf};
use std::process::ExitCode;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

const PASTA_PADRAO: &str = "/data/local/tmp/a12m";
const ARQ_EPISODIOS: &str = "episodios.jsonl";
const ARQ_PID: &str = "a12m.pid";
const ARQ_TRAVA: &str = "a12m.lock";
/// Teto do arquivo de episodios; passou, vira episodios.1.jsonl (so 2 arquivos, < 512 KB no total).
const TETO_ARQUIVO: u64 = 256 * 1024;

/// Abertura de episodio pelo TEMPO DE ESPERA no intervalo (diferenca do total= do PSI), que pega pico curto entre duas
/// leituras: memoria >= 3% (~1 s de espera em 30 s), cpu >= 20%, disco >= 10%. Ou pela media avg10 alta no instante
/// (mem 10, cpu 60, disco 30). Fecha quando tudo cai abaixo da metade (histerese). Repouso do A12 em 20/11: cpu 1-2,
/// mem 0-1, disco 0-1.
const ESPERA_MEM: f64 = 3.0;
const ESPERA_CPU: f64 = 20.0;
const ESPERA_IO: f64 = 10.0;
const AVG_MEM: f64 = 10.0;
const AVG_CPU: f64 = 60.0;
const AVG_IO: f64 = 30.0;

/// Calor (24/11, pedido do Rafael "temperatura a cada 15 s"): abre com bateria >= 42 C ou processador (AP) >= 48 C e fecha
/// abaixo de 40 e 45 (histerese). O saude.py avisa a bateria em 40 C e alerta em 45; o SDHMS da Samsung fecha o app visivel
/// no calor. Memoria livre baixa: abre abaixo de 500 MB disponiveis (atencao do saude.py) e fecha a partir de 650.
const CALOR_BAT: f64 = 42.0;
const CALOR_AP: f64 = 48.0;
const MEM_BAIXA_MB: u64 = 500;
const MEM_OK_MB: u64 = 650;

/// Episodio com histerese: Some(true) = abriu agora, Some(false) = fechou agora, None = nada mudou.
fn passo(aberto: bool, alto: bool, calmo: bool) -> Option<bool> {
    match (aberto, alto, calmo) {
        (false, true, _) => Some(true),
        (true, _, true) => Some(false),
        _ => None,
    }
}

fn agora_s() -> u64 {
    SystemTime::now().duration_since(UNIX_EPOCH).map(|d| d.as_secs()).unwrap_or(0)
}

fn agora() -> String {
    leitura::iso_brasilia(agora_s())
}

fn valor_de(args: &[String], chave: &str) -> Option<u64> {
    texto_de(args, chave).and_then(|v| v.parse().ok())
}

fn texto_de<'a>(args: &'a [String], chave: &str) -> Option<&'a str> {
    args.iter().position(|a| a == chave).and_then(|i| args.get(i + 1)).map(String::as_str)
}

fn pasta() -> PathBuf {
    std::env::var_os("A12M_PASTA").map(PathBuf::from).unwrap_or_else(|| PathBuf::from(PASTA_PADRAO))
}

/// Pasta e arquivos so do shell (0700/0600): a linha do tempo de episodios e dado de uso do aparelho.
#[cfg(unix)]
fn preparar_pasta(p: &Path) -> std::io::Result<()> {
    use std::os::unix::fs::{DirBuilderExt, PermissionsExt};
    fs::DirBuilder::new().recursive(true).mode(0o700).create(p)?;
    fs::set_permissions(p, fs::Permissions::from_mode(0o700))?;
    // arquivos criados antes (versao 0.1 saia com 0666): fecha tambem; o binario fica 0700
    for e in fs::read_dir(p)?.flatten() {
        let modo = if e.file_name() == "a12m" { 0o700 } else { 0o600 };
        let _ = fs::set_permissions(e.path(), fs::Permissions::from_mode(modo));
    }
    Ok(())
}

#[cfg(not(unix))]
fn preparar_pasta(p: &Path) -> std::io::Result<()> {
    fs::create_dir_all(p)
}

fn abrir_privado(caminho: &Path, anexar: bool) -> std::io::Result<File> {
    let mut o = OpenOptions::new();
    o.create(true);
    if anexar {
        o.append(true);
    } else {
        o.write(true).truncate(true);
    }
    #[cfg(unix)]
    {
        use std::os::unix::fs::OpenOptionsExt;
        o.mode(0o600);
    }
    o.open(caminho)
}

/// Trava exclusiva do vigia (flock): so um vigia por vez, sem corrida entre conferir e gravar. O fd fica aberto
/// enquanto o vigia vive; o kernel solta sozinho quando ele morre.
#[cfg(unix)]
fn travar(p: &Path) -> Option<File> {
    use std::os::unix::io::AsRawFd;
    extern "C" {
        fn flock(fd: i32, op: i32) -> i32;
    }
    let f = abrir_privado(&p.join(ARQ_TRAVA), true).ok()?;
    // SAFETY: flock(2) recebe o fd de um arquivo aberto que continua vivo (f) e uma constante. LOCK_EX|LOCK_NB = 2|4.
    let ok = unsafe { flock(f.as_raw_fd(), 2 | 4) } == 0;
    ok.then_some(f)
}

#[cfg(not(unix))]
fn travar(p: &Path) -> Option<File> {
    abrir_privado(&p.join(ARQ_TRAVA), true).ok()
}

/// O vigia que esta rodando: o arquivo guarda "pid starttime" e os dois tem de bater com /proc (pid reaproveitado
/// depois de reiniciar, por um sh do adb ou qualquer outro, nao passa por vigia).
fn vigia_vivo(p: &Path) -> Option<u32> {
    let txt = fs::read_to_string(p.join(ARQ_PID)).ok()?;
    let mut c = txt.split_whitespace();
    let pid: u32 = c.next()?.parse().ok()?;
    let inicio: u64 = c.next()?.parse().ok()?;
    (pid != std::process::id() && leitura::inicio_processo(&sistema::ler(&format!("/proc/{pid}/stat"))) == Some(inicio))
        .then_some(pid)
}

fn gravar(p: &Path, linha: &str) {
    let arq = p.join(ARQ_EPISODIOS);
    if fs::metadata(&arq).map(|m| m.len() > TETO_ARQUIVO).unwrap_or(false) {
        let _ = fs::rename(&arq, p.join("episodios.1.jsonl"));
    }
    if let Ok(mut f) = abrir_privado(&arq, true) {
        let _ = writeln!(f, "{linha}");
    }
}

/// (some de cpu, mem, io) do PSI: medias e totais.
fn pressoes() -> [leitura::Pressao; 3] {
    [
        leitura::pressao(&sistema::ler("/proc/pressure/cpu")).0,
        leitura::pressao(&sistema::ler("/proc/pressure/memory")).0,
        leitura::pressao(&sistema::ler("/proc/pressure/io")).0,
    ]
}

/// Episodio de pressao aberto: inicio (parede, em s), picos de espera % (cpu, mem, io) e de avg10.
struct Episodio {
    inicio_s: u64,
    pico_espera: [f64; 3],
    pico_avg10: [f64; 3],
}

fn lista(v: &[(String, f64)]) -> String {
    sistema::lista_json(v, "cpu_pct")
}

fn vigiar(args: &[String]) -> ExitCode {
    let p = pasta();
    if preparar_pasta(&p).is_err() {
        eprintln!("nao consegui criar {} (rode como shell: adb shell)", p.display());
        return ExitCode::from(2);
    }
    let Some(_trava) = travar(&p) else {
        println!("o vigia ja esta rodando{}", vigia_vivo(&p).map(|pid| format!(" (pid {pid})")).unwrap_or_default());
        return ExitCode::SUCCESS;
    };
    let eu = std::process::id();
    let inicio = leitura::inicio_processo(&sistema::ler(&format!("/proc/{eu}/stat"))).unwrap_or(0);
    if abrir_privado(&p.join(ARQ_PID), false).and_then(|mut f| write!(f, "{eu} {inicio}")).is_err() {
        eprintln!("nao consegui gravar o pid em {}", p.display());
        return ExitCode::from(2);
    }
    let calmo = Duration::from_secs(valor_de(args, "--intervalo").unwrap_or(15).clamp(5, 600));
    let atento = Duration::from_secs(10);
    let mut tuneis_antes = leitura::tuneis(&sistema::ler("/proc/net/dev"));
    gravar(&p, &format!(
        "{{\"evento\":\"vigia_ligado\",\"quando\":{},\"intervalo_s\":{},\"tuneis\":{}}}",
        sistema::js(&agora()), calmo.as_secs(), sistema::textos_json(&tuneis_antes)
    ));
    let mut aberto: Option<Episodio> = None;
    let mut calor: Option<(u64, f64, f64)> = None; // inicio, pico do AP, pico da bateria
    let mut baixa: Option<(u64, u64)> = None; // inicio, minimo disponivel em MB
    let mut antes = pressoes();
    let mut t_antes = Instant::now();
    loop {
        // sleep usa o relogio monotonico: nao conta o tempo dormindo e nunca acorda o aparelho (sem wakelock nem alarme)
        std::thread::sleep(if aberto.is_some() { atento } else { calmo });
        let agora_p = pressoes();
        let t = Instant::now();
        let us = u64::try_from((t - t_antes).as_micros()).unwrap_or(u64::MAX);
        let espera: [f64; 3] = std::array::from_fn(|i| leitura::espera_pct(antes[i].total_us, agora_p[i].total_us, us));
        let avg10: [f64; 3] = std::array::from_fn(|i| agora_p[i].avg10);
        antes = agora_p;
        t_antes = t;
        let alto = espera[0] >= ESPERA_CPU || espera[1] >= ESPERA_MEM || espera[2] >= ESPERA_IO
            || avg10[0] >= AVG_CPU || avg10[1] >= AVG_MEM || avg10[2] >= AVG_IO;
        let calmo_agora = espera[0] < ESPERA_CPU / 2.0 && espera[1] < ESPERA_MEM / 2.0 && espera[2] < ESPERA_IO / 2.0
            && avg10[0] < AVG_CPU / 2.0 && avg10[1] < AVG_MEM / 2.0 && avg10[2] < AVG_IO / 2.0;
        match aberto.as_mut() {
            None if alto => {
                // so na abertura le os ~600 processos (duas varreduras com 1 s, sem o cmdline de todos)
                let t0 = Instant::now();
                let p0 = sistema::processos();
                std::thread::sleep(Duration::from_secs(1));
                let t1 = Instant::now();
                let mut p1 = sistema::processos();
                p1.remove(&eu);
                let (top_cpu, top_ram) = sistema::maiores(&p0, &p1, t1 - t0, 5);
                let disp = leitura::memoria(&sistema::ler("/proc/meminfo")).disponivel_mb;
                gravar(&p, &format!(
                    "{{\"evento\":\"inicio\",\"quando\":{},\"espera_pct\":{{\"cpu\":{},\"mem\":{},\"io\":{}}},\"avg10\":{{\"cpu\":{},\"mem\":{},\"io\":{}}},\"mem_disponivel_mb\":{disp},\"maiores_cpu\":{},\"maiores_ram\":{}}}",
                    sistema::js(&agora()), espera[0], espera[1], espera[2], avg10[0], avg10[1], avg10[2],
                    lista(&top_cpu), sistema::lista_json(&top_ram, "mb")
                ));
                aberto = Some(Episodio { inicio_s: agora_s(), pico_espera: espera, pico_avg10: avg10 });
            }
            Some(ep) => {
                for i in 0..3 {
                    ep.pico_espera[i] = ep.pico_espera[i].max(espera[i]);
                    ep.pico_avg10[i] = ep.pico_avg10[i].max(avg10[i]);
                }
                if calmo_agora {
                    let (e, a) = (ep.pico_espera, ep.pico_avg10);
                    // duracao pelo relogio de parede (coerente com "quando"; inclui o tempo em que o aparelho dormiu)
                    gravar(&p, &format!(
                        "{{\"evento\":\"fim\",\"quando\":{},\"duracao_s\":{},\"pico_espera_pct\":{{\"cpu\":{},\"mem\":{},\"io\":{}}},\"pico_avg10\":{{\"cpu\":{},\"mem\":{},\"io\":{}}}}}",
                        sistema::js(&agora()), agora_s().saturating_sub(ep.inicio_s), e[0], e[1], e[2], a[0], a[1], a[2]
                    ));
                    aberto = None;
                }
            }
            None => {}
        }
        sinais(&p, &mut tuneis_antes, &mut calor, &mut baixa);
    }
}

/// Tuneis da VPN, calor e memoria livre baixa: so grava quando algo muda (abre ou fecha), nunca a cada leitura.
fn sinais(p: &Path, tuneis_antes: &mut Vec<String>, calor: &mut Option<(u64, f64, f64)>, baixa: &mut Option<(u64, u64)>) {
    let tun = leitura::tuneis(&sistema::ler("/proc/net/dev"));
    if tun != *tuneis_antes {
        gravar(p, &format!(
            "{{\"evento\":\"tuneis\",\"quando\":{},\"agora\":{},\"antes\":{}}}",
            sistema::js(&agora()), sistema::textos_json(&tun), sistema::textos_json(tuneis_antes)
        ));
        *tuneis_antes = tun;
    }
    let temps = sistema::temperaturas();
    if !temps.is_empty() {
        // sem leitura (dumpsys falhou) nao abre nem fecha nada
        let (ap, bat) = (leitura::grau(&temps, "AP"), leitura::grau(&temps, "BAT"));
        match passo(calor.is_some(), bat >= CALOR_BAT || ap >= CALOR_AP, bat < CALOR_BAT - 2.0 && ap < CALOR_AP - 3.0) {
            Some(true) => {
                gravar(p, &format!(
                    "{{\"evento\":\"calor_inicio\",\"quando\":{},\"temperatura_c\":{}}}",
                    sistema::js(&agora()), sistema::temps_json(&temps)
                ));
                *calor = Some((agora_s(), ap, bat));
            }
            Some(false) => {
                if let Some((ini, pa, pb)) = calor.take() {
                    gravar(p, &format!(
                        "{{\"evento\":\"calor_fim\",\"quando\":{},\"duracao_s\":{},\"pico_c\":{{\"AP\":{},\"BAT\":{}}}}}",
                        sistema::js(&agora()), agora_s().saturating_sub(ini), pa.max(ap), pb.max(bat)
                    ));
                }
            }
            None => {
                if let Some(c) = calor.as_mut() {
                    c.1 = c.1.max(ap);
                    c.2 = c.2.max(bat);
                }
            }
        }
    }
    let mem = leitura::memoria(&sistema::ler("/proc/meminfo"));
    if mem.total_mb > 0 {
        let disp = mem.disponivel_mb;
        match passo(baixa.is_some(), disp < MEM_BAIXA_MB, disp >= MEM_OK_MB) {
            Some(true) => {
                gravar(p, &format!(
                    "{{\"evento\":\"memoria_baixa_inicio\",\"quando\":{},\"mem_disponivel_mb\":{disp},\"swap_usado_mb\":{}}}",
                    sistema::js(&agora()), mem.swap_usado_mb()
                ));
                *baixa = Some((agora_s(), disp));
            }
            Some(false) => {
                if let Some((ini, minimo)) = baixa.take() {
                    gravar(p, &format!(
                        "{{\"evento\":\"memoria_baixa_fim\",\"quando\":{},\"duracao_s\":{},\"minimo_mb\":{}}}",
                        sistema::js(&agora()), agora_s().saturating_sub(ini), minimo.min(disp)
                    ));
                }
            }
            None => {
                if let Some(b) = baixa.as_mut() {
                    b.1 = b.1.min(disp);
                }
            }
        }
    }
}

#[cfg(test)]
mod testes {
    use super::passo;

    #[test]
    fn episodio_com_histerese() {
        assert_eq!(passo(false, true, false), Some(true), "abre quando passa do limite");
        assert_eq!(passo(false, false, true), None, "fechado e calmo: nada");
        assert_eq!(passo(true, true, false), None, "aberto e ainda alto: segue aberto");
        assert_eq!(passo(true, false, false), None, "entre os dois limites: segue aberto (histerese)");
        assert_eq!(passo(true, false, true), Some(false), "fecha so abaixo do limite de baixo");
    }
}

fn episodios(args: &[String]) -> ExitCode {
    let n: usize = args.get(2).and_then(|v| v.parse().ok()).unwrap_or(20);
    let p = pasta();
    let mut linhas: Vec<String> = Vec::new();
    for nome in ["episodios.1.jsonl", ARQ_EPISODIOS] {
        linhas.extend(sistema::ler(&p.join(nome).to_string_lossy()).lines().map(str::to_string));
    }
    if linhas.is_empty() {
        println!("nenhum episodio gravado em {}", p.display());
    }
    let ini = linhas.len().saturating_sub(n);
    for l in &linhas[ini..] {
        println!("{l}");
    }
    ExitCode::SUCCESS
}

fn custo() -> ExitCode {
    let Some(pid) = vigia_vivo(&pasta()) else {
        println!("o vigia nao esta rodando");
        return ExitCode::from(1);
    };
    let stat = sistema::ler(&format!("/proc/{pid}/stat"));
    let (Some((_, cpu, rss)), Some(inicio)) = (leitura::processo(&stat), leitura::inicio_processo(&stat)) else {
        println!("nao consegui ler /proc/{pid}/stat");
        return ExitCode::from(1);
    };
    let uptime: f64 = sistema::ler("/proc/uptime").split_whitespace().next().and_then(|v| v.parse().ok()).unwrap_or(0.0);
    let vivo_s = (uptime - inicio as f64 / 100.0).max(1.0);
    let pct = (cpu as f64 / 100.0) / vivo_s * 100.0;
    println!(
        "vigia pid {pid}: RSS {:.1} MB | CPU media {:.4}% de um nucleo | {:.2} h no ar | {} jiffies de CPU",
        (rss * 4) as f64 / 1024.0, pct, vivo_s / 3600.0, cpu
    );
    ExitCode::SUCCESS
}

fn parar() -> ExitCode {
    let p = pasta();
    let Some(pid) = vigia_vivo(&p) else {
        println!("o vigia nao esta rodando");
        return ExitCode::SUCCESS;
    };
    if sinal_term(pid) {
        let _ = fs::remove_file(p.join(ARQ_PID));
        gravar(&p, &format!("{{\"evento\":\"vigia_parado\",\"quando\":{}}}", sistema::js(&agora())));
        println!("vigia parado (pid {pid})");
        ExitCode::SUCCESS
    } else {
        eprintln!("nao consegui parar o pid {pid}");
        ExitCode::from(1)
    }
}

#[cfg(unix)]
fn sinal_term(pid: u32) -> bool {
    extern "C" {
        fn kill(pid: i32, sig: i32) -> i32;
    }
    let Ok(pid) = i32::try_from(pid) else { return false };
    // SAFETY: kill(2) so recebe dois inteiros; o pid foi conferido (pid + starttime) como sendo o vigia a12m.
    unsafe { kill(pid, 15) == 0 }
}

#[cfg(not(unix))]
fn sinal_term(_pid: u32) -> bool {
    false
}

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().collect();
    match args.get(1).map(String::as_str).unwrap_or("status") {
        "status" => {
            let janela = Duration::from_secs(valor_de(&args, "--janela").unwrap_or(2).clamp(1, 60));
            let f = sistema::foto(janela);
            if args.iter().any(|a| a == "--json") {
                println!("{}", f.json(&agora(), texto_de(&args, "--rotulo").unwrap_or("a12m")));
            } else {
                println!("{}", f.texto());
            }
            ExitCode::SUCCESS
        }
        "vigiar" => vigiar(&args),
        "episodios" => episodios(&args),
        "custo" => custo(),
        "parar" => parar(),
        "conferir" => {
            for (k, v) in sistema::conferir() {
                println!("{k:<40} {}", if v.is_empty() { "(sem acesso ou nao existe)" } else { &v });
            }
            ExitCode::SUCCESS
        }
        "versao" | "--version" => {
            println!("a12m {}", env!("CARGO_PKG_VERSION"));
            ExitCode::SUCCESS
        }
        _ => {
            eprintln!("uso: a12m [status [--json] [--janela S] [--rotulo R] | vigiar [--intervalo S] | episodios [N] | custo | parar | conferir | versao]");
            ExitCode::from(64)
        }
    }
}
