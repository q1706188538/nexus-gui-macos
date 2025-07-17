import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import subprocess
import threading
import os
import re
import sys
import requests
import json


class NexusGUI:
    def __init__(self, master):
        self.master = master
        self.master.title("Nexus Network GUI")
        self.master.geometry("1200x850")
        self.master.minsize(600, 550)

        self.process = None
        self.stats_labels = {}
        
        if getattr(sys, 'frozen', False):
            # If the application is run as a bundle, the PyInstaller bootloader
            # extends the sys module by a flag frozen=True and sets the app 
            # path into variable _MEIPASS'.
            application_path = sys._MEIPASS
        else:
            application_path = os.path.dirname(os.path.abspath(__file__))
        
        self.cli_path = os.path.join(application_path, "nexus-network-mac")

        # Set up a dedicated, persistent path for user data
        if sys.platform == 'darwin':
            # For macOS, save in the standard Application Support directory
            home_dir = os.path.expanduser("~")
            self.data_dir = os.path.join(home_dir, "Library", "Application Support", "NexusGUI")
        else:
            # For other OSes (like Windows), save alongside the executable
            self.data_dir = application_path

        # Ensure the data directory exists
        os.makedirs(self.data_dir, exist_ok=True)
        
        self.node_ids_path = os.path.join(self.data_dir, "node_ids.txt")
        self.settings_path = os.path.join(self.data_dir, "settings.json")

        self.create_menubar()
        self.create_widgets()
        self.load_node_ids()
        self.load_settings()

    def create_menubar(self):
        menubar = tk.Menu(self.master)
        self.master.config(menu=menubar)

        # App Menu (for macOS)
        app_menu = tk.Menu(menubar, name='apple')
        menubar.add_cascade(label="NexusGUI", menu=app_menu)
        app_menu.add_command(label="关于 NexusGUI", command=self.show_about)
        app_menu.add_separator()
        app_menu.add_command(label="退出 NexusGUI", command=self.on_closing)

        # Edit Menu
        edit_menu = tk.Menu(menubar, name='edit')
        menubar.add_cascade(label="编辑", menu=edit_menu)
        edit_menu.add_command(label="撤销", accelerator="Cmd+Z", command=lambda: self.master.focus_get().event_generate("<<Undo>>"))
        edit_menu.add_command(label="重做", accelerator="Cmd+Y", command=lambda: self.master.focus_get().event_generate("<<Redo>>"))
        edit_menu.add_separator()
        edit_menu.add_command(label="剪切", accelerator="Cmd+X", command=lambda: self.master.focus_get().event_generate("<<Cut>>"))
        edit_menu.add_command(label="复制", accelerator="Cmd+C", command=lambda: self.master.focus_get().event_generate("<<Copy>>"))
        edit_menu.add_command(label="粘贴", accelerator="Cmd+V", command=lambda: self.master.focus_get().event_generate("<<Paste>>"))
        edit_menu.add_separator()
        edit_menu.add_command(label="全选", accelerator="Cmd+A", command=lambda: self.master.focus_get().event_generate("<<SelectAll>>"))


    def create_widgets(self):
        # This is the correct and standard way to build a complex Tkinter UI
        # to avoid geometry manager conflicts.
        # 1. Create a main content frame.
        # 2. Use .pack() to make this frame fill the entire window. This is the *only* time we will use .pack().
        # 3. All other widgets will be placed inside this frame using .grid().
        content_frame = tk.Frame(self.master, padx=10, pady=10)
        content_frame.pack(fill=tk.BOTH, expand=True)

        # Configure the grid layout for a two-column setup
        content_frame.grid_rowconfigure(0, weight=1)
        content_frame.grid_columnconfigure(0, weight=1, minsize=450)
        content_frame.grid_columnconfigure(1, weight=2)

        # --- Left Panel ---
        # The notebook will be on the left
        self.notebook = ttk.Notebook(content_frame)
        self.notebook.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        start_control_tab = tk.Frame(self.notebook, padx=10, pady=10)
        user_node_mgmt_tab = tk.Frame(self.notebook, padx=10, pady=10)

        self.notebook.add(start_control_tab, text='启动控制')
        self.notebook.add(user_node_mgmt_tab, text='用户与节点管理')

        self.create_start_control_tab(start_control_tab)
        self.create_user_node_mgmt_tab(user_node_mgmt_tab)
        
        # --- Right Panel ---
        # The output frame will be on the right
        output_frame = tk.LabelFrame(content_frame, text="输出日志", padx=5, pady=5)
        output_frame.grid(row=0, column=1, sticky="nsew")
        
        # Configure the output_frame's grid so the text widget inside expands
        output_frame.grid_rowconfigure(0, weight=1)
        output_frame.grid_columnconfigure(0, weight=1)

        self.output_text = scrolledtext.ScrolledText(output_frame, state=tk.DISABLED, wrap=tk.WORD)
        self.output_text.grid(row=0, column=0, sticky="nsew")

    def create_start_control_tab(self, parent_frame):
        # Main container frame for this tab
        main_container = tk.Frame(parent_frame)
        main_container.pack(fill=tk.BOTH, expand=True)
        main_container.grid_columnconfigure(0, weight=1)

        control_frame = tk.LabelFrame(main_container, text="控制面板", padx=5, pady=5)
        control_frame.grid(row=0, column=0, sticky="ew")
        control_frame.grid_columnconfigure(1, weight=1)

        ttk.Label(control_frame, text="Node IDs:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.node_ids_text = scrolledtext.ScrolledText(control_frame, height=5, width=60, wrap=tk.WORD)
        self.node_ids_text.grid(row=0, column=1, columnspan=2, padx=5, pady=5, sticky="ew")

        self.proxy_enabled = tk.BooleanVar()
        proxy_check = ttk.Checkbutton(control_frame, text="使用代理", variable=self.proxy_enabled, command=self.toggle_proxy)
        proxy_check.grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)

        self.proxy_url_label = ttk.Label(control_frame, text="代理地址 (Proxy URL):")
        self.proxy_url_label.grid(row=2, column=0, padx=5, pady=5, sticky=tk.W)
        self.proxy_url_entry = ttk.Entry(control_frame, width=50)
        self.proxy_url_entry.grid(row=2, column=1, padx=5, pady=5, sticky="ew")
        
        proxy_format_hint = ttk.Label(control_frame, text="代理地址格式为 用户名@主机:端口 或 s5://用户名@主机:端口", font=("TkDefaultFont", 9), foreground="gray")
        proxy_format_hint.grid(row=3, column=1, padx=5, pady=(0, 5), sticky="w")

        self.proxy_user_pwd_label = ttk.Label(control_frame, text="代理密码 (Proxy Pwd):")
        self.proxy_user_pwd_label.grid(row=4, column=0, padx=5, pady=5, sticky=tk.W)
        self.proxy_user_pwd_entry = ttk.Entry(control_frame, width=50)
        self.proxy_user_pwd_entry.grid(row=4, column=1, padx=5, pady=5, sticky="ew")
        
        proxy_button_frame = ttk.Frame(control_frame)
        proxy_button_frame.grid(row=4, column=2, padx=5, pady=5, sticky="w")
        
        self.test_proxy_button = ttk.Button(proxy_button_frame, text="测试代理", command=self.test_proxy)
        self.test_proxy_button.grid(row=0, column=0, padx=(0, 5))

        self.save_settings_button = ttk.Button(proxy_button_frame, text="保存设置", command=self.save_settings)
        self.save_settings_button.grid(row=0, column=1)

        self.restart_enabled = tk.BooleanVar()
        restart_check = ttk.Checkbutton(control_frame, text="定时重启 (小时):", variable=self.restart_enabled)
        restart_check.grid(row=5, column=0, padx=5, pady=5, sticky=tk.W)
        self.restart_interval_entry = ttk.Entry(control_frame, width=10)
        self.restart_interval_entry.grid(row=5, column=1, padx=5, pady=5, sticky=tk.W)
        self.restart_interval_entry.insert(0, "5")

        button_frame = ttk.Frame(control_frame)
        button_frame.grid(row=6, column=0, columnspan=3, pady=10)

        self.start_button = ttk.Button(button_frame, text="启动", command=self.start_cli)
        self.start_button.grid(row=0, column=0, padx=5)

        self.stop_button = ttk.Button(button_frame, text="停止", command=self.stop_cli, state=tk.DISABLED)
        self.stop_button.grid(row=0, column=1, padx=5)
        
        self.save_ids_button = ttk.Button(button_frame, text="保存列表", command=self.save_node_ids)
        self.save_ids_button.grid(row=0, column=2, padx=5)

        # --- Statistics Frame ---
        stats_frame = tk.LabelFrame(main_container, text="统计信息", padx=5, pady=5)
        stats_frame.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        stats_frame.grid_columnconfigure(1, weight=1)

        stats_map = {
            "total_tasks_fetched": "成功获取的任务数量:",
            "unique_tasks_fetched": "唯一的任务数量:",
            "duplicate_tasks_fetched": "重复获取的任务数量:",
            "successful_submissions": "成功提交的任务数量:",
            "failed_submissions": "提交失败的任务数量:",
        }
        
        row = 0
        for key, text in stats_map.items():
            label = ttk.Label(stats_frame, text=text)
            label.grid(row=row, column=0, sticky="w", padx=5, pady=2)
            value_label = ttk.Label(stats_frame, text="N/A", anchor="w")
            value_label.grid(row=row, column=1, sticky="ew", padx=5, pady=2)
            self.stats_labels[key] = value_label
            row += 1

        refresh_stats_button = ttk.Button(stats_frame, text="刷新统计", command=self.fetch_stats)
        refresh_stats_button.grid(row=row, column=0, columnspan=2, pady=10)

        self.toggle_proxy()

    def create_user_node_mgmt_tab(self, parent_frame):
        user_frame = tk.LabelFrame(parent_frame, text="用户注册 (register-user)", padx=5, pady=5)
        user_frame.grid(row=0, column=0, sticky="ew", padx=0, pady=5)

        ttk.Label(user_frame, text="钱包地址:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.wallet_address_entry = ttk.Entry(user_frame, width=50)
        self.wallet_address_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        
        register_user_button = ttk.Button(user_frame, text="注册用户", command=self.handle_register_user)
        register_user_button.grid(row=0, column=2, padx=5, pady=5)

        node_frame = tk.LabelFrame(parent_frame, text="节点管理 (register-node)", padx=5, pady=5)
        node_frame.grid(row=1, column=0, sticky="ew", padx=0, pady=(15, 5))

        ttk.Label(node_frame, text="创建数量:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.node_count_entry = ttk.Entry(node_frame, width=10)
        self.node_count_entry.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        self.node_count_entry.insert(0, "1")

        register_node_button = ttk.Button(node_frame, text="批量创建和提取Node ID", command=self.handle_register_nodes)
        register_node_button.grid(row=1, column=0, columnspan=3, pady=10)

    def toggle_proxy(self):
        state = tk.NORMAL if self.proxy_enabled.get() else tk.DISABLED
        for child in [self.proxy_url_label, self.proxy_url_entry, self.proxy_user_pwd_label, self.proxy_user_pwd_entry, self.test_proxy_button]:
            child.config(state=state)

    def log(self, message):
        self.output_text.config(state=tk.NORMAL)
        self.output_text.insert(tk.END, message + "\n")
        self.output_text.see(tk.END)
        self.output_text.config(state=tk.DISABLED)
        self.master.update_idletasks()

    def start_cli(self):
        if not os.path.exists(self.cli_path):
             messagebox.showerror("错误", f"未找到CLI程序: {self.cli_path}\n请确保 'nexus-network-mac' 文件与本程序位于同一目录下，或在打包时已正确包含。")
             return

        node_ids_str = self.node_ids_text.get("1.0", tk.END).strip()
        if not node_ids_str:
            messagebox.showerror("错误", "Node IDs不能为空。")
            return
        
        node_ids = node_ids_str.split()
        cmd = [self.cli_path, "start", "--headless", "--node-ids"] + node_ids

        if self.proxy_enabled.get():
            proxy_url = self.proxy_url_entry.get().strip()
            if not proxy_url:
                messagebox.showerror("错误", "代理URL不能为空。")
                return
            
            cmd.extend(["--proxy-url", proxy_url])

            proxy_user_pwd = self.proxy_user_pwd_entry.get().strip()
            if proxy_user_pwd:
                cmd.extend(["--proxy-user-pwd", proxy_user_pwd])

        try:
            creationflags = 0
            if sys.platform == "win32":
                creationflags = subprocess.CREATE_NO_WINDOW
            
            self.log(f"执行命令: {' '.join(cmd)}")
            self.process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1, universal_newlines=True, creationflags=creationflags)
            
            threading.Thread(target=self.read_output, args=(self.process.stdout,), daemon=True).start()
            threading.Thread(target=self.read_output, args=(self.process.stderr,), daemon=True).start()

            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)

            if self.restart_enabled.get():
                try:
                    interval_hours = float(self.restart_interval_entry.get())
                    interval_seconds = interval_hours * 3600
                    self.log(f"已启用定时重启，将在 {interval_hours} 小时后重启。")
                    self.restart_timer = threading.Timer(interval_seconds, self.restart_cli)
                    self.restart_timer.start()
                except ValueError:
                    messagebox.showerror("错误", "重启时间间隔必须是数字。")
                    self.stop_cli()

        except Exception as e:
            messagebox.showerror("启动失败", str(e))
            self.log(f"启动失败: {e}")

    def read_output(self, pipe):
        for line in iter(pipe.readline, ''):
            self.log(line.strip())
        pipe.close()

    def stop_cli(self, restarting=False):
        if hasattr(self, 'restart_timer') and self.restart_timer.is_alive():
            self.restart_timer.cancel()
            
        if self.process:
            self.log("正在停止CLI...")
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.log("强制终止CLI...")
                self.process.kill()
            self.process = None
            self.log("CLI已停止。")

        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        if not restarting:
            self.log("--------------------")

    def restart_cli(self):
        self.log("开始定时重启...")
        self.stop_cli(restarting=True)
        # Give some time for resources to be released
        self.master.after(2000, self.start_cli)

    def save_node_ids(self):
        try:
            node_ids = self.node_ids_text.get("1.0", tk.END).strip()
            with open(self.node_ids_path, "w") as f:
                f.write(node_ids)
            self.log("Node ID列表已保存。")
            messagebox.showinfo("成功", "Node ID列表已成功保存！")
        except Exception as e:
            self.log(f"保存Node ID失败: {e}")
            messagebox.showerror("错误", f"保存Node ID失败: {e}")

    def load_node_ids(self):
        if os.path.exists(self.node_ids_path):
            try:
                with open(self.node_ids_path, "r") as f:
                    node_ids = f.read()
                if node_ids:
                    self.node_ids_text.delete("1.0", tk.END)
                    self.node_ids_text.insert("1.0", node_ids)
                    self.log("已成功加载上次保存的Node ID列表。")
            except Exception as e:
                self.log(f"加载Node IDs时发生未知错误: {e}")

    def save_settings(self):
        """Saves the current settings (proxy, restart) to a file."""
        settings = {
            "proxy": {
                "enabled": self.proxy_enabled.get(),
                "url": self.proxy_url_entry.get().strip(),
                "password": self.proxy_user_pwd_entry.get().strip()
            },
            "restart": {
                "enabled": self.restart_enabled.get(),
                "interval_hours": self.restart_interval_entry.get().strip()
            }
        }
        try:
            with open(self.settings_path, "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=4)
            self.log("设置已保存。")
        except Exception as e:
            messagebox.showerror("保存失败", f"无法保存设置: {e}")
            self.log(f"保存设置失败: {e}")

    def load_settings(self):
        """Loads settings from a file on startup."""
        self.log(f"正在读取设置文件: {self.settings_path}")
        if not os.path.exists(self.settings_path):
            return

        try:
            with open(self.settings_path, "r", encoding="utf-8") as f:
                raw_content = f.read()
            self.log(f"读取到的内容: {raw_content}")
            settings = json.loads(raw_content)
            
            # Load proxy settings
            proxy_info = settings.get("proxy", {})
            self.proxy_enabled.set(proxy_info.get("enabled", False))
            self.proxy_url_entry.delete(0, tk.END)
            self.proxy_url_entry.insert(0, proxy_info.get("url", ""))
            self.log(f"赋值后proxy_url_entry内容: {self.proxy_url_entry.get()}")

            self.proxy_user_pwd_entry.delete(0, tk.END)
            self.proxy_user_pwd_entry.insert(0, proxy_info.get("password", ""))
            self.log(f"赋值后proxy_user_pwd_entry内容: {self.proxy_user_pwd_entry.get()}")
            
            # Load restart settings
            restart_info = settings.get("restart", {})
            self.restart_enabled.set(restart_info.get("enabled", False))
            self.restart_interval_entry.delete(0, tk.END)
            self.restart_interval_entry.insert(0, restart_info.get("interval_hours", "5"))

            # Apply the proxy enabled/disabled state AFTER loading all values
            self.toggle_proxy()

            self.log("已加载保存的设置。")

        except (json.JSONDecodeError, KeyError) as e:
            self.log(f"加载设置失败: 文件格式错误或内容不完整 - {e}")
        except Exception as e:
            self.log(f"加载设置时发生未知错误: {e}")

    def on_closing(self):
        if self.process:
             if messagebox.askokcancel("退出", "CLI进程仍在运行。确定要退出吗？"):
                self.stop_cli()
                self.master.destroy()
        else:
            self.master.destroy()

    def handle_register_user(self):
        threading.Thread(target=self.register_user_thread, daemon=True).start()

    def handle_register_nodes(self):
        threading.Thread(target=self.register_nodes_thread, daemon=True).start()

    def run_management_command(self, cmd):
        self.log(f"执行命令: {' '.join(cmd)}")
        try:
            creationflags = 0
            if sys.platform == "win32":
                creationflags = subprocess.CREATE_NO_WINDOW
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, universal_newlines=True, creationflags=creationflags)
            
            output_lines = []
            for line in iter(process.stdout.readline, ''):
                clean_line = line.strip()
                self.log(clean_line)
                output_lines.append(clean_line)
            
            process.stdout.close()
            process.wait()
            
            if process.returncode != 0:
                self.log(f"命令执行失败，返回码: {process.returncode}")
            
            return output_lines

        except FileNotFoundError:
            messagebox.showerror("错误", f"未找到CLI程序: {self.cli_path}")
            return None
        except Exception as e:
            self.log(f"执行命令时发生错误: {e}")
            messagebox.showerror("错误", f"执行命令时发生错误: {e}")
            return None

    def register_user_thread(self):
        wallet_address = self.wallet_address_entry.get().strip()
        if not re.match(r"^0x[a-fA-F0-9]{40}$", wallet_address):
            self.log("错误: 无效的钱包地址。")
            messagebox.showerror("错误", "无效的钱包地址。它必须是一个以 '0x' 开头的42个字符的十六进制字符串。")
            return
            
        cmd = [self.cli_path, "register-user", "--wallet-address", wallet_address]
        self.run_management_command(cmd)
        self.log("用户注册命令执行完毕。")

    def register_nodes_thread(self):
        try:
            count = int(self.node_count_entry.get())
            if count <= 0: raise ValueError
        except ValueError:
            messagebox.showerror("错误", "创建数量必须是一个正整数。")
            return

        newly_created_ids = []
        for i in range(count):
            self.log(f"--- 正在创建第 {i+1}/{count} 个节点 ---")
            cmd = [self.cli_path, "register-node"]
            output = self.run_management_command(cmd)

            if output:
                found_id = None
                for line in output:
                    if "node" in line.lower() and "id" in line.lower():
                        match = re.search(r'\b\d{7,}\b', line)
                        if match:
                            found_id = match.group(0)
                            self.log(f"成功提取 Node ID: {found_id}")
                            newly_created_ids.append(found_id)
                            break
                if not found_id:
                    self.log("警告: 未能在命令输出中找到新的 Node ID。")

        if newly_created_ids:
            self.log(f"成功创建 {len(newly_created_ids)} 个新的 Node ID: {', '.join(newly_created_ids)}")
            
            current_ids = self.node_ids_text.get("1.0", tk.END).strip()
            new_ids_str = " ".join(newly_created_ids)
            updated_ids = (current_ids + " " + new_ids_str) if current_ids else new_ids_str
            
            self.node_ids_text.delete("1.0", tk.END)
            self.node_ids_text.insert("1.0", updated_ids)
            
            self.log("新的 Node ID 已自动填充到 '启动控制' 选项卡。")
            self.notebook.select(0)
        
        self.log("批量创建节点操作完成。")

    def show_about(self):
        about_message = "Nexus Network GUI\n\n版本: 1.1.0\n一个用于简化 'nexus-network-mac' CLI 操作的图形界面工具。"
        messagebox.showinfo("关于 NexusGUI", about_message)
        
    def test_proxy(self):
        """Starts the proxy test in a separate thread."""
        if not self.proxy_enabled.get():
            messagebox.showinfo("提示", "请先勾选 '使用代理'。")
            return
        threading.Thread(target=self._test_proxy_thread, daemon=True).start()

    def _test_proxy_thread(self):
        """Handles the logic for testing the proxy connection."""
        proxy_url_str = self.proxy_url_entry.get().strip()
        if not proxy_url_str:
            self.master.after(0, lambda: messagebox.showwarning("警告", "请输入代理URL。"))
            return

        proxy_pwd = self.proxy_user_pwd_entry.get().strip()
        
        user = None
        host_port = proxy_url_str
        if '@' in proxy_url_str:
            try:
                user, host_port = proxy_url_str.split('@', 1)
            except ValueError:
                self.master.after(0, lambda: messagebox.showerror("错误", "代理URL格式无效。"))
                return

        scheme = "http" # Assume http proxy, as requests library supports this for https traffic as well.
        
        if user and proxy_pwd:
            proxy_for_requests = f"{scheme}://{user}:{proxy_pwd}@{host_port}"
        elif user:
            proxy_for_requests = f"{scheme}://{user}@{host_port}"
        else:
            proxy_for_requests = f"{scheme}://{host_port}"

        proxies = {'http': proxy_for_requests, 'https': proxy_for_requests}
        test_url = "https://ipinfo.io/json"
        
        self.log(f"正在测试代理: {proxy_for_requests} ...")
        try:
            response = requests.get(test_url, proxies=proxies, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            info_str = "\n".join([f"{k}: {v}" for k, v in data.items()])
            self.log("代理测试成功。")
            self.master.after(0, lambda: messagebox.showinfo("代理测试成功", f"代理工作正常！\n\nIP信息:\n{info_str}"))

        except requests.exceptions.ProxyError as e:
            error_message = f"代理连接失败。请检查地址、端口和认证信息。\n错误: {e}"
            self.log(error_message)
            self.master.after(0, lambda: messagebox.showerror("代理测试失败", error_message))
        except requests.exceptions.Timeout:
            error_message = "请求超时。请检查代理服务器和网络连接。"
            self.log(error_message)
            self.master.after(0, lambda: messagebox.showerror("代理测试失败", error_message))
        except Exception as e:
            error_message = f"发生未知错误: {e}"
            self.log(error_message)
            self.master.after(0, lambda: messagebox.showerror("代理测试失败", error_message))

    def fetch_stats(self):
        """Starts the statistics fetching in a separate thread."""
        threading.Thread(target=self._fetch_stats_thread, daemon=True).start()

    def _fetch_stats_thread(self):
        """Handles the logic for fetching stats from the CLI."""
        stats_url = "http://127.0.0.1:38080/stats"
        self.log("正在获取统计信息...")
        
        if not self.process or self.process.poll() is not None:
            self.log("CLI程序未运行，无法获取统计信息。")
            self.master.after(0, self.reset_stats_labels)
            return
            
        try:
            response = requests.get(stats_url, timeout=5)
            response.raise_for_status()
            stats = response.json()
            self.log("成功获取统计信息。")
            self.master.after(0, self.update_stats_labels, stats)

        except requests.exceptions.RequestException as e:
            self.log(f"获取统计信息失败: {e}")
            self.master.after(0, self.reset_stats_labels)
        except json.JSONDecodeError:
            self.log("获取统计信息失败: 响应内容不是有效的JSON格式。")
            self.master.after(0, self.reset_stats_labels)
        except Exception as e:
            self.log(f"处理统计信息时出错: {e}")
            self.master.after(0, self.reset_stats_labels)

    def update_stats_labels(self, stats):
        """Updates the statistics labels on the GUI."""
        for key, label in self.stats_labels.items():
            label.config(text=str(stats.get(key, "错误")))

    def reset_stats_labels(self):
        """Resets statistics labels to 'N/A'."""
        for label in self.stats_labels.values():
            label.config(text="N/A")


if __name__ == "__main__":
    try:
        root = tk.Tk()
        app = NexusGUI(root)
        root.protocol("WM_DELETE_WINDOW", app.on_closing)

        # --- macOS 焦点修复 ---
        # 这是一个针对 Tkinter 在 macOS 上臭名昭著的 bug 的解决方案
        # 该 bug 会导致应用程序窗口在启动时无法自动获得焦点。
        if sys.platform == 'darwin': # 'darwin' 是 macOS 的系统名称
            def force_focus():
                # 将窗口强制置于最前
                root.lift()
                # 暂时将其设置为置顶窗口
                root.attributes('-topmost', True)
                # 在短暂延迟后，取消置顶，使其行为正常
                root.after(10, lambda: root.attributes('-topmost', False))
                # 强制窗口获取焦点
                root.focus_force()

            # 安排焦点修复在主循环开始时立即运行
            root.after(0, force_focus)

        root.mainloop()
    except Exception as e:
        import traceback
        import sys
        # On macOS, the current working directory for a bundled app might not be what you expect.
        # It's safer to write the log file next to the executable itself if possible.
        if hasattr(sys, '_MEIPASS'):
            # Path to executable in a PyInstaller bundle
            exe_dir = os.path.dirname(sys.executable)
            log_path = os.path.join(exe_dir, "gui_error.log")
        else:
            # Path for running from source
            log_path = "gui_error.log"
        
        with open(log_path, "w", encoding="utf-8") as f:
            f.write("NexusGUI an unexpected error occurred:\n")
            f.write(str(e) + "\n\n")
            f.write(traceback.format_exc())