import time
from dataclasses import dataclass, field
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path

# -----------------------------
# Primos + hash
# -----------------------------
def _eh_primo(n: int) -> bool:
    if n <= 1: return False
    if n <= 3: return True
    if n % 2 == 0 or n % 3 == 0: return False
    i = 5
    while i * i <= n:
        if n % i == 0 or n % (i + 2) == 0: return False
        i += 6
    return True

def _proximo_primo(n: int) -> int:
    n = max(2, n + (n % 2 == 0))
    while not _eh_primo(n): n += 2
    return n

def hash_djb2(chave: str, nb: int) -> int:
    h = 5381
    for c in chave: h = ((h << 5) + h) + ord(c)  # h*33+c
    return h % nb

# -----------------------------
# Estruturas do índice
# -----------------------------
@dataclass
class BucketPage:
    FR: int
    slots: dict[str, int] = field(default_factory=dict)
    next: "BucketPage | None" = None
    def cheio(self) -> bool: return len(self.slots) >= self.FR

@dataclass
class IndiceHash:
    NB: int
    FR: int
    diretorio: list[BucketPage]
    paginas: list[list[str]]

def criar_paginas(lista: list[str], tam_pagina: int) -> list[list[str]]:
    tam = max(1, tam_pagina)
    return [lista[i:i+tam] for i in range(0, len(lista), tam)]

def _iter_chain(head: BucketPage):
    p = head
    while p:
        yield p
        p = p.next

def _bucket_insert(head: BucketPage, chave: str, id_pagina: int):
    for pg in _iter_chain(head):
        if chave in pg.slots: return
    pg = head
    while pg.cheio():
        if not pg.next: pg.next = BucketPage(head.FR)
        pg = pg.next
    pg.slots[chave] = id_pagina

def construir_indice(paginas: list[list[str]], nb: int, fr: int) -> IndiceHash:
    dire = [BucketPage(fr) for _ in range(nb)]
    for id_pag, pagina in enumerate(paginas):
        for palavra in pagina:
            _bucket_insert(dire[hash_djb2(palavra, nb)], palavra, id_pag)
    return IndiceHash(nb, fr, dire, paginas)

# -----------------------------
# Métricas
# -----------------------------
def metricas_globais(indice: IndiceHash, NR: int) -> dict:
    # NU = nº de chaves efetivamente indexadas (únicas)
    NU = 0
    total_col = 0
    buck_ovf = 0
    nonempty_buckets = 0

    for head in indice.diretorio:
        chs_bucket = 0
        paginas_bucket = 0
        is_first_page = True

        # Itera sobre a cadeia de páginas do bucket
        for pg in _iter_chain(head):
            num_chaves_pagina = len(pg.slots)
            chs_bucket += num_chaves_pagina
            paginas_bucket += 1

            if not is_first_page:
                total_col += num_chaves_pagina
            
            is_first_page = False

        if chs_bucket > 0:
            nonempty_buckets += 1
            # A lógica antiga de colisão foi removida daqui.
            # total_col += (chs_bucket - 1)  <-- LÓGICA ANTIGA E REMOVIDA

        if paginas_bucket > 1:
            buck_ovf += 1
            
        NU += chs_bucket

    # Denominador correto: NU, não NR
    colisoes_pct = (total_col / NU * 100.0) if NU > 0 else 0.0
    overflow_pct = (buck_ovf / indice.NB * 100.0) if indice.NB > 0 else 0.0

    return {
        "colisoes_globais_pct": colisoes_pct,
        "overflow_buckets_pct": overflow_pct,
        "total_colisoes": total_col,
        "buckets_com_overflow": buck_ovf,
        "NU": NU,
        "nonempty_buckets": nonempty_buckets,
        "NR": NR,
    }




# -----------------------------
# Buscas
# -----------------------------
def buscar_indice(ind: IndiceHash, chave: str) -> dict:
    t0 = time.perf_counter()
    addr = hash_djb2(chave, ind.NB)
    head = ind.diretorio[addr]

    total_bucket_pages = 0
    cadeia_bucket_keys = []
    for p in _iter_chain(head):
        total_bucket_pages += 1
        cadeia_bucket_keys.append(list(p.slots.keys()))

    ovf_pages = max(0, total_bucket_pages - 1)

    # 2. Realizamos a busca pela chave na cadeia.
    lidas = 0
    pg = head
    while pg:
        lidas += 1
        if chave in pg.slots:
            # Chave encontrada: retorna sucesso com as métricas já calculadas
            return {
                "encontrado": True, "localizacao": pg.slots[chave], "custo": lidas,
                "tempo": time.perf_counter() - t0,
                "overflow_local_count": ovf_pages,
                "taxa_overflow_local_pct": (ovf_pages / total_bucket_pages * 100.0) if total_bucket_pages > 0 else 0.0,
                "endereco_bucket": addr,
                "cadeia_bucket": cadeia_bucket_keys,
            }
        pg = pg.next
        
    # Chave não encontrada: retorna falha com as mesmas métricas
    return {
        "encontrado": False, "localizacao": None, "custo": lidas,
        "tempo": time.perf_counter() - t0,
        "overflow_local_count": ovf_pages,
        "taxa_overflow_local_pct": (ovf_pages / total_bucket_pages * 100.0) if total_bucket_pages > 0 else 0.0,
        "endereco_bucket": addr,
        "cadeia_bucket": cadeia_bucket_keys,
    }

def table_scan(paginas: list[list[str]], chave: str, listar=False) -> dict:
    t0 = time.perf_counter()
    lidos = []
    for id_pag, pagina in enumerate(paginas):
        for palavra in pagina:
            if listar: lidos.append(palavra)
            if palavra == chave:
                return {"encontrado": True, "localizacao": id_pag, "custo": id_pag+1,
                        "tempo": time.perf_counter() - t0, "registros_lidos": lidos}
    return {"encontrado": False, "localizacao": None, "custo": len(paginas),
            "tempo": time.perf_counter() - t0, "registros_lidos": lidos}

# -----------------------------
# GUI
# -----------------------------
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Índice Hash Estático")
        self.geometry("1024x768")

        self.lista: list[str] = []
        self.paginas: list[list[str]] = []
        self.NR = 0
        self.indice: IndiceHash | None = None
        self.nb = 0

        self.var_tam = tk.IntVar(value=20)
        self.var_fr = tk.IntVar(value=10)
        self.var_chave = tk.StringVar()

        self._ui()

    def _ui(self):
        top = ttk.Frame(self, padding=8); top.pack(side=tk.TOP, fill=tk.X)
        ttk.Label(top, text="Tamanho da página:").pack(side=tk.LEFT, padx=(0,4))
        ttk.Spinbox(top, from_=1, to=10000, textvariable=self.var_tam, width=6).pack(side=tk.LEFT)
        ttk.Button(top, text="Carregar words.txt", command=self._carregar).pack(side=tk.LEFT, padx=8)

        bar = ttk.Frame(self, padding=8); bar.pack(fill=tk.X)
        ttk.Label(bar, text="FR por bucket:").pack(side=tk.LEFT)
        ttk.Spinbox(bar, from_=1, to=1000, textvariable=self.var_fr, width=6).pack(side=tk.LEFT, padx=4)
        ttk.Label(bar, text="NB (> NR/FR):").pack(side=tk.LEFT, padx=(12,4))
        self.lbl_nb = ttk.Label(bar, text="—"); self.lbl_nb.pack(side=tk.LEFT)
        ttk.Button(bar, text="Construir Índice", command=self._construir).pack(side=tk.LEFT, padx=12)
        self.lbl_status = ttk.Label(bar, text="Status: aguardando"); self.lbl_status.pack(side=tk.LEFT, padx=8)

        ttk.Separator(self, orient="horizontal").pack(fill=tk.X, pady=4)

        panes = ttk.PanedWindow(self, orient=tk.HORIZONTAL); panes.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(panes, padding=6); panes.add(left, weight=1)
        frameDados = ttk.LabelFrame(left, text="Páginas de DADOS (primeira e última)"); frameDados.pack(fill=tk.BOTH, padx=4, pady=4)
        self.text_primeira = tk.Text(frameDados, height=12, wrap="none"); self.text_primeira.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4, pady=4)
        self.text_ultima = tk.Text(frameDados, height=12, wrap="none"); self.text_ultima.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4, pady=4)

        frameGlobais = ttk.LabelFrame(left, text="Estatísticas Globais"); frameGlobais.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self.text_globais = tk.Text(frameGlobais, height=10, wrap="word"); self.text_globais.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        right = ttk.Frame(panes, padding=6); panes.add(right, weight=1)
        frameBusca = ttk.LabelFrame(right, text="Busca"); frameBusca.pack(fill=tk.X, padx=4, pady=4)
        ttk.Label(frameBusca, text="Chave:").pack(side=tk.LEFT, padx=4)
        ttk.Entry(frameBusca, textvariable=self.var_chave, width=32).pack(side=tk.LEFT, padx=4)
        ttk.Button(frameBusca, text="Índice", command=self._buscar_indice).pack(side=tk.LEFT, padx=4)
        ttk.Button(frameBusca, text="Table Scan", command=self._table_scan).pack(side=tk.LEFT, padx=4)

        frameRel = ttk.LabelFrame(right, text="Relatório"); frameRel.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self.text_rel = tk.Text(frameRel, height=14, wrap="word"); self.text_rel.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        frameBucket = ttk.LabelFrame(right, text="Cadeia do Bucket"); frameBucket.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self.tree_bucket = ttk.Treeview(frameBucket, columns=("conteudo",), show="tree headings", height=8)
        self.tree_bucket.heading("#0", text="Página")
        self.tree_bucket.heading("conteudo", text="Chaves")
        self.tree_bucket.column("#0", width=140); self.tree_bucket.column("conteudo", width=480)
        self.tree_bucket.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        frameScan = ttk.LabelFrame(right, text="Registros lidos no Table Scan"); frameScan.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self.list_scan = tk.Listbox(frameScan, height=10); self.list_scan.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

    def _carregar(self):
        words_path = Path(__file__).resolve().parent / "words.txt"
        with open(words_path, "r", encoding="utf-8") as f:
             self.lista = [l.rstrip("\n") for l in f]
        self.NR = len(self.lista)
        self.paginas = criar_paginas(self.lista, int(self.var_tam.get()))
        self._mostrar_paginas()
        self.indice = None; self.nb = 0; self.lbl_nb.config(text="—")
        self.text_globais.delete("1.0", tk.END); self.text_rel.delete("1.0", tk.END)
        for it in self.tree_bucket.get_children(): self.tree_bucket.delete(it)
        self.list_scan.delete(0, tk.END)
        self._atualiza_status(f"Dados: NR={self.NR}, páginas={len(self.paginas)}, tam={max(1,int(self.var_tam.get()))}")
        self._calcular_nb()

    def _mostrar_paginas(self):
        self.text_primeira.delete("1.0", tk.END); self.text_ultima.delete("1.0", tk.END)
        if not self.paginas:
            for t in (self.text_primeira, self.text_ultima): t.insert(tk.END, "Nenhuma página.\n"); return
        pri = self.paginas[0]; ult = self.paginas[-1]
        self.text_primeira.insert(tk.END, f"PÁGINA #0 | {len(pri)} registros\n" + "-"*50 + "\n" + "\n".join(f"{i+1:>5}: {p}" for i,p in enumerate(pri)))
        self.text_ultima.insert(tk.END, f"PÁGINA #{len(self.paginas)-1} | {len(ult)} registros\n" + "-"*50 + "\n" + "\n".join(f"{i+1:>5}: {p}" for i,p in enumerate(ult)))

    def _calcular_nb(self):
        if self.NR <= 0: return
        fr = max(1, int(self.var_fr.get()))
        base = self.NR // fr + 1
        self.nb = _proximo_primo(base)
        self.lbl_nb.config(text=str(self.nb))
        self._atualiza_status(f"NB calculado: {self.nb} (FR={fr})")

    def _construir(self):
        if not self.paginas:
            messagebox.showinfo("Info", "Carregue os dados.")
            return
        self._calcular_nb()
        fr = max(1, int(self.var_fr.get()))
        self.indice = construir_indice(self.paginas, self.nb, fr)
        m = metricas_globais(self.indice, self.NR)
        self._mostrar_metricas(m)
        self._atualiza_status(f"Índice construído: NB={self.nb}, FR={fr}")

    def _mostrar_metricas(self, m: dict):
        t = self.text_globais
        t.delete("1.0", tk.END)
        t.insert(tk.END, f"NR: {self.NR} | NB: {self.nb}\n")
        t.insert(tk.END, f"- Colisões globais: {m['total_colisoes']} ({m['colisoes_globais_pct']:.2f}%)\n")
        t.insert(tk.END, f"- Buckets com overflow: {m['buckets_com_overflow']} de {self.nb} ({m['overflow_buckets_pct']:.2f}%)\n")

    def _buscar_indice(self):
        self._limpar_relatorios()
        if not self.indice:
            messagebox.showinfo("Info", "Construa o índice primeiro."); return
        chave = self.var_chave.get().strip()
        if not chave:
            messagebox.showinfo("Info", "Digite a chave."); return
        r_idx = buscar_indice(self.indice, chave)
        r_scan = table_scan(self.paginas, chave, listar=True)
        self._mostrar_relatorio(r_idx, r_scan)
        self._mostrar_bucket(r_idx)
        self._mostrar_scan_list(r_scan)

    def _table_scan(self):
        self._limpar_relatorios()
        if not self.paginas:
            messagebox.showinfo("Info", "Carregue os dados primeiro."); return
        chave = self.var_chave.get().strip()
        if not chave:
            messagebox.showinfo("Info", "Digite a chave."); return
        r_scan = table_scan(self.paginas, chave, listar=True)
        rel = ["[Resultados e Custos]", f"  - Table Scan: {'Encontrada na página '+str(r_scan['localizacao']) if r_scan['encontrado'] else 'Não encontrada.'} (Custo: {r_scan['custo']} páginas)","",
               "[Tempo]", f"  - Table Scan: {r_scan['tempo']:.6f}s"]
        self.text_rel.insert(tk.END, "\n".join(rel))
        self._mostrar_scan_list(r_scan)

    def _limpar_relatorios(self):
        self.text_rel.delete("1.0", tk.END)
        self.list_scan.delete(0, tk.END)
        for it in self.tree_bucket.get_children(): self.tree_bucket.delete(it)

    def _mostrar_bucket(self, r_idx: dict):
        self.tree_bucket.insert("", "end", text=f"Bucket #{r_idx['endereco_bucket']}", values=("cadeia",))
        for i, keys in enumerate(r_idx["cadeia_bucket"], 1):
            conteudo = ", ".join(keys[:20]) + (" ..." if len(keys) > 20 else "")
            self.tree_bucket.insert("", "end", text=f"Cadeia {i}", values=(conteudo,))

    def _mostrar_scan_list(self, r_scan: dict, limite=5000):
        lst = r_scan.get("registros_lidos", [])
        for i, w in enumerate(lst, 1):
            if i > limite:
                self.list_scan.insert(tk.END, f"... ({len(lst)-limite} restantes)")
                break
            self.list_scan.insert(tk.END, w)

    def _mostrar_relatorio(self, r_idx: dict, r_scan: dict):
        msg_idx = f"Encontrada na página {r_idx['localizacao']}" if r_idx['encontrado'] else "Não encontrada."
        msg_scan = f"Encontrada na página {r_scan['localizacao']}" if r_scan['encontrado'] else "Não encontrada."
        diff = r_scan['tempo'] - r_idx['tempo']
        rel = [
            "--- RELATÓRIO ---", "",
            "[Resultados e Custos]",
            f"  - Índice: {msg_idx} (Custo: {r_idx['custo']} páginas)",
            f"  - Table Scan: {msg_scan} (Custo: {r_scan['custo']} páginas)",
            "",
            "[Bucket acessado]",
            f"  - Páginas de Overflow: {r_idx['overflow_local_count']}  | Taxa: {r_idx['taxa_overflow_local_pct']:.2f}% (FR={self.indice.FR})",
            "",
            "[Tempo]",
            f"  - Índice: {r_idx['tempo']:.6f}s  | Table Scan: {r_scan['tempo']:.6f}s",
            f"  - Diferença: {diff:+.6f}s (positivo = índice mais rápido)",
        ]
        self.text_rel.insert(tk.END, "\n".join(rel))

    def _atualiza_status(self, msg: str): self.lbl_status.config(text=msg)

# -----------------------------
# Main
# -----------------------------
if __name__ == "__main__":
    App().mainloop()
