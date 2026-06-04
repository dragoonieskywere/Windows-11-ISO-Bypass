import os
import shutil
import threading
import subprocess
import time
import tempfile
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
import io
import re

try:
    import pycdlib
    PYCDLIB_AVAILABLE = True
except ImportError:
    PYCDLIB_AVAILABLE = False

class AppBypassISO(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("Windows 11 ISO Bypass")
        self.geometry("550x450")
        
        # Variáveis
        self.caminho_iso_orig = tk.StringVar()
        self.caminho_iso_dest = tk.StringVar()

        # --- ABAS (TABVIEW) ---
        self.tabview = ctk.CTkTabview(self, width=500, height=350)
        self.tabview.pack(pady=10, padx=20, fill="both", expand=True)
        
        self.tab_main = self.tabview.add("Main")
        self.tab_about = self.tabview.add("About")

        # ==========================================
        # ABA PRINCIPAL (MAIN)
        # ==========================================
        self.lbl_orig = ctk.CTkLabel(self.tab_main, text="Original ISO:")
        self.lbl_orig.pack(pady=(15, 5))
        
        self.btn_orig = ctk.CTkButton(self.tab_main, text="Select ISO", command=self.selecionar_origem)
        self.btn_orig.pack(pady=5)
        
        self.lbl_dest = ctk.CTkLabel(self.tab_main, text="Save New ISO As:")
        self.lbl_dest.pack(pady=(15, 5))
        
        self.btn_dest = ctk.CTkButton(self.tab_main, text="Select Destination", command=self.selecionar_destino)
        self.btn_dest.pack(pady=5)
        
        self.btn_iniciar = ctk.CTkButton(self.tab_main, text="Start Process", fg_color="green", hover_color="darkgreen", command=self.iniciar_processo_wrapper)
        self.btn_iniciar.pack(pady=20)
        
        self.lbl_status_geral = ctk.CTkLabel(self.tab_main, text="Waiting...")
        self.lbl_status_geral.pack(pady=5)
        
        self.progress_bar = ctk.CTkProgressBar(self.tab_main, width=400)
        self.progress_bar.pack(pady=10)
        self.progress_bar.set(0)

        # ==========================================
        # ABA SOBRE (ABOUT)
        # ==========================================
        about_text = "Tool developed by:\n\nGregório Severiano (Dragoonie)\n\nVersion 1.0\n© 2026"
        self.lbl_about = ctk.CTkLabel(
            self.tab_about, 
            text=about_text,
            font=ctk.CTkFont(size=18, weight="bold"),
            justify="center"
        )
        self.lbl_about.pack(expand=True)

    # --- LÓGICA DO PROGRAMA ---
    def selecionar_origem(self):
        caminho = filedialog.askopenfilename(filetypes=[("ISO Files", "*.iso")])
        if caminho:
            # Mostra o status de validação ao utilizador
            self.lbl_status_geral.configure(text="Validating ISO...")
            self.update() 
            
            # Valida se é o Windows 11
            is_win11, msg = self._is_windows_11_iso(caminho)
            
            if is_win11:
                # ISO Válida
                self.caminho_iso_orig.set(caminho)
                self.lbl_orig.configure(text=f"Original ISO: {os.path.basename(caminho)}")
                self.lbl_status_geral.configure(text=msg)
            else:
                # ISO Inválida (Linux, Win10, etc)
                self.caminho_iso_orig.set("")
                self.lbl_orig.configure(text="Original ISO:")
                self.lbl_status_geral.configure(text="Validation failed.")
                messagebox.showerror("Invalid ISO", msg)

    def selecionar_destino(self):
        caminho = filedialog.asksaveasfilename(defaultextension=".iso", filetypes=[("ISO Files", "*.iso")])
        if caminho:
            self.caminho_iso_dest.set(caminho)
            self.lbl_dest.configure(text=f"Save New ISO As: {os.path.basename(caminho)}")

    def _make_writable(self, file_path):
        try:
            os.chmod(file_path, 0o666)
        except Exception:
            pass

    def iniciar_processo_wrapper(self):
        src = self.caminho_iso_orig.get()
        dst = self.caminho_iso_dest.get()

        if not src or not dst:
            messagebox.showwarning("Warning", "Select the source ISO and destination before starting.")
            return

        if not PYCDLIB_AVAILABLE:
            msg = "To modify the ISO without breaking the Boot, the 'pycdlib' library is required.\n\nOpen your terminal/CMD and type:\npip install pycdlib"
            messagebox.showerror("Missing Dependency", msg)
            self.lbl_status_geral.configure(text="Error: pycdlib not installed.")
            return

        self.btn_iniciar.configure(state="disabled")
        threading.Thread(target=self._process_iso, args=(src, dst), daemon=True).start()

    def _is_windows_11_iso(self, iso_path):
        """Lê o setup.exe da raiz da ISO e valida se a Build é do Windows 11 (>= 22000)"""
        iso = pycdlib.PyCdlib()
        try:
            iso.open(iso_path)
            extracted_fp = io.BytesIO()
            
            paths_to_test = [
                ('/SETUP.EXE', 'udf_path'),
                ('/setup.exe', 'udf_path'),
                ('/SETUP.EXE;1', 'iso_path'),
                ('/SETUP.EXE', 'joliet_path')
            ]
            
            file_found = False
            for path, path_type in paths_to_test:
                try:
                    iso.get_file_from_iso_fp(extracted_fp, **{path_type: path})
                    file_found = True
                    break
                except Exception:
                    continue
                    
            iso.close()
            
            if not file_found:
                return False, "Invalid ISO: 'setup.exe' not found in the root directory."
                
            file_bytes = extracted_fp.getvalue()
            # Limpa bytes nulos (UTF-16) para podermos ler a string da versão
            text_rough = file_bytes.replace(b'\x00', b'').decode('ascii', errors='ignore')
            
            match = re.search(r'10\.0\.(\d{5})', text_rough)
            
            if match:
                build_number = int(match.group(1))
                if build_number >= 22000:
                    return True, f"Windows 11 detected (Build {build_number})."
                else:
                    return False, f"Windows 10 ISO detected (Build {build_number}).\nThis tool is designed exclusively for Windows 11."
            else:
                return False, "Could not determine the Windows build version from setup.exe."
                
        except Exception as e:
            return False, f"Failed to read ISO structure:\n{str(e)}"

    def _process_iso(self, src, dst):
        """Procura os bytes do appraiserres.dll via UDF e zera a DLL fisicamente na nova ISO"""
        try:
            # 1. Extrair a assinatura da DLL do Windows 11
            self.lbl_status_geral.configure(text="Reading original ISO structure...")
            self.progress_bar.set(0.10)
            
            iso = pycdlib.PyCdlib()
            iso.open(src)
            
            extracted_fp = io.BytesIO()
            file_found = False
            
            paths_to_test = [
                ('/SOURCES/APPRAISERRES.DLL', 'udf_path'),
                ('/sources/appraiserres.dll', 'udf_path'),
                ('/SOURCES/APPRAISERRES.DLL;1', 'iso_path'),
                ('/SOURCES/APPRAISERRES.DLL', 'joliet_path'),
            ]
            
            for path, path_type in paths_to_test:
                try:
                    iso.get_file_from_iso_fp(extracted_fp, **{path_type: path})
                    file_found = True
                    break
                except Exception:
                    continue
                    
            iso.close()
            
            if not file_found:
                self.progress_bar.set(0)
                self.lbl_status_geral.configure(text="Error: DLL not found!")
                messagebox.showerror("Error", "Could not find 'appraiserres.dll' in the ISO.\nAre you sure this is a Windows 11 ISO?")
                self.btn_iniciar.configure(state="normal")
                return

            file_bytes = extracted_fp.getvalue()
            file_size = len(file_bytes)
            
            chunk_size = min(256 * 1024, file_size)
            signature = file_bytes[:chunk_size]

            # 2. Copiar a ISO
            self.lbl_status_geral.configure(text="Copying original ISO (this may take a few minutes)...")
            self.progress_bar.set(0.30)

            shutil.copy2(src, dst)
            self._make_writable(dst)

            self.progress_bar.set(0.80)

            # 3. Procurar a assinatura física na nova ISO e zerar os bytes
            self.lbl_status_geral.configure(text="Applying Bypass patch (zeroing DLL)...")
            
            patched = False
            if file_size == 0:
                patched = True 
            else:
                buffer_size = 10 * 1024 * 1024 
                overlap = len(signature) - 1
                
                with open(dst, 'r+b') as f:
                    pos = 0
                    while True:
                        f.seek(pos)
                        data = f.read(buffer_size)
                        if not data:
                            break
                            
                        idx = data.find(signature)
                        if idx != -1:
                            physical_offset = pos + idx
                            f.seek(physical_offset)
                            f.write(b'\x00' * file_size)
                            patched = True
                            break
                            
                        pos += buffer_size - overlap

            self.progress_bar.set(1.0)
            if patched:
                self.lbl_status_geral.configure(text="ISO generated successfully!")
                messagebox.showinfo("Success", f"Bypass ISO successfully created at:\n{dst}\n\nDLL was successfully zeroed out!")
            else:
                self.lbl_status_geral.configure(text="Warning: Patch failed!")
                messagebox.showwarning("Warning", "ISO was copied, but failed to locate physical DLL to overwrite.")

        except Exception as e:
            self.progress_bar.set(0)
            self.lbl_status_geral.configure(text="An error occurred.")
            messagebox.showerror("Error", f"An error occurred while generating the ISO:\n{str(e)}")
        finally:
            self.btn_iniciar.configure(state="normal")

if __name__ == "__main__":
    app = AppBypassISO()
    app.mainloop()