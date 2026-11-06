using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Net.Http;
using System.Windows.Forms;

namespace AdminPanel;

public sealed class CommandItem
{
    [JsonPropertyName("command")] public string Command { get; set; } = "";
    [JsonPropertyName("level")] public int Level { get; set; }
    [JsonPropertyName("category")] public string Category { get; set; } = "";
}
public sealed class AppConfig
{
    public string Language { get; set; } = "ru";
    public int Level { get; set; } = 1;
    public string ChatKey { get; set; } = "T";
    public int KeyDelayMs { get; set; } = 80;
    public int CooldownMs { get; set; } = 300;
    public bool AutoChat { get; set; } = true;
    public bool AutoStart { get; set; }
    public bool Sound { get; set; }
    public bool CheckUpdates { get; set; } = true;
    public string LastNotifiedVersion { get; set; } = "";
    public Dictionary<string,string> Binds { get; set; } = new() { ["act:toggle"] = "Insert" };
    public List<string> Favorites { get; set; } = new();
    public List<string> CustomCommands { get; set; } = new();
    public List<DateTime> Reports { get; set; } = new();
    public List<string> Notes { get; set; } = new();
}
public sealed class MainForm : Form
{
    const int WM_HOTKEY = 0x0312;
    const int HOTKEY_ID = 0xA101;
    const int MOD_NOREPEAT = 0x4000;
    readonly Dictionary<int,string> registeredBinds = new();
    const string AppDirName = "AdminPanel";
    static readonly Color Bg = Color.FromArgb(0,0,0), Panel = Color.FromArgb(13,13,13),
        Border = Color.FromArgb(43,43,43), TextMain = Color.White,
        Muted = Color.FromArgb(160,160,160), Accent = Color.FromArgb(250,228,200);
    readonly string dataDir = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), AppDirName);
    readonly string configPath;
    AppConfig config = new();
    List<CommandItem> commands = new();
    readonly Panel sidebar = new(), content = new();
    Panel? rootSurface;
    readonly Label title = new();
    readonly TextBox search = new();
    readonly FlowLayoutPanel tiles = new();
    readonly Dictionary<string,Button> nav = new();
    readonly ToolTip commandTip = new() { InitialDelay = 0, ReshowDelay = 0, AutoPopDelay = 12000, ShowAlways = true };
    Panel? bindOverlay;
    Label? bindOverlayText;
    string? pendingBindCommand;
    Button? pendingBindButton;
    Panel? updateToast;
    System.Windows.Forms.Timer? toastTimer;
    bool compactMode;
    DateTime lastHotkey = DateTime.MinValue;

    [DllImport("user32.dll", SetLastError=true)] static extern bool RegisterHotKey(IntPtr hWnd,int id,uint fsModifiers,uint vk);
    [DllImport("user32.dll", SetLastError=true)] static extern bool UnregisterHotKey(IntPtr hWnd,int id);
    [DllImport("user32.dll")] static extern void keybd_event(byte bVk,byte bScan,uint dwFlags,UIntPtr dwExtraInfo);
    const uint KEYEVENTF_KEYUP=0x0002;
    public MainForm()
    {
        configPath=Path.Combine(dataDir,"config.json");
        Directory.CreateDirectory(dataDir); LoadConfig(); LoadCommands();
        Text="Admin Panel"; MinimumSize=new Size(900,600); Size=new Size(1120,740);
        var appIconPath = Path.Combine(AppContext.BaseDirectory, "Assets", "AdminPanel.ico");
        if (File.Exists(appIconPath)) { try { Icon = new Icon(appIconPath); } catch { } }
        BackColor=Bg; ForeColor=TextMain; Font=new Font("Segoe UI",9.5f);
        FormBorderStyle=FormBorderStyle.Sizable; StartPosition=FormStartPosition.CenterScreen;
        BuildShell(); ShowCommands(); RegisterToggle();
        Shown += async (_,_) => await CheckForUpdatesAsync();
        Resize += (_,_) => PositionUpdateToast();
        KeyPreview = true; KeyDown += HandleBindKeyDown;
        FormClosing += (_,_)=>{ UnregisterHotKey(Handle,HOTKEY_ID); SaveConfig(); };
    }
    void LoadConfig()
    {
        try { if(File.Exists(configPath)) config=JsonSerializer.Deserialize<AppConfig>(File.ReadAllText(configPath)) ?? new(); } catch {}
    }
    void SaveConfig()
    {
        try { Directory.CreateDirectory(dataDir); File.WriteAllText(configPath,JsonSerializer.Serialize(config,new JsonSerializerOptions{WriteIndented=true})); } catch {}
    }
    void LoadCommands()
    {
        try {
            var p=Path.Combine(AppContext.BaseDirectory,"commands.json");
            commands=JsonSerializer.Deserialize<List<CommandItem>>(File.ReadAllText(p)) ?? new();
        } catch { commands=new(); }
        commands.AddRange(config.CustomCommands.Select(c=>new CommandItem{Command=c,Level=config.Level,Category="custom"}));
    }
    void BuildShell()
    {
        var root=new Panel{Dock=DockStyle.Fill,BackColor=Bg,Padding=new Padding(12)}; rootSurface=root; Controls.Add(root);
        sidebar.Width=205; sidebar.Dock=DockStyle.Left; sidebar.BackColor=Panel; sidebar.Padding=new Padding(12);
        root.Controls.Add(sidebar);
        var brand = new Panel { Dock = DockStyle.Top, Height = 52, BackColor = Panel };
        var logoPath = Path.Combine(AppContext.BaseDirectory, "Assets", "AdminPanelLogo.png");
        if (File.Exists(logoPath))
        {
            var logo = new PictureBox { Left = 0, Top = 8, Width = 36, Height = 36, SizeMode = PictureBoxSizeMode.Zoom, BackColor = Color.Transparent };
            using (var stream = new FileStream(logoPath, FileMode.Open, FileAccess.Read, FileShare.ReadWrite))
            using (var memory = new MemoryStream()) { stream.CopyTo(memory); memory.Position = 0; using var sourceImage = Image.FromStream(memory); logo.Image = new Bitmap(sourceImage); }
            brand.Controls.Add(logo);
        }
        var brandText = new Label { Text = "ADMIN PANEL", Left = 44, Top = 0, Width = 145, Height = 52, ForeColor = Accent, Font = new Font("Segoe UI Semibold", 13), TextAlign = ContentAlignment.MiddleLeft };
        brand.Controls.Add(brandText);
        sidebar.Controls.Add(brand);
        AddNav("Команды","commands"); AddNav("Избранное","favorites"); AddNav("Репорты","reports"); AddNav("Заметки","notes"); AddNav("Настройки","settings");
        content.Dock=DockStyle.Fill; content.BackColor=Bg; content.Padding=new Padding(24,8,8,8); root.Controls.Add(content);
        title.Dock=DockStyle.Top; title.Height=48; title.Font=new Font("Segoe UI Semibold",20); title.ForeColor=TextMain; content.Controls.Add(title);
        search.Dock=DockStyle.Top; search.Height=36; search.BackColor=Panel; search.ForeColor=TextMain; search.BorderStyle=BorderStyle.FixedSingle; search.PlaceholderText="Поиск команды...";
        search.TextChanged+=(_,_)=>ShowCommandTiles(); content.Controls.Add(search);
        tiles.Dock=DockStyle.Fill; tiles.AutoScroll=true; tiles.WrapContents=true; tiles.FlowDirection=FlowDirection.LeftToRight; tiles.Padding=new Padding(0,18,0,0); content.Controls.Add(tiles);
    }
    void AddNav(string text,string key)
    {
        var b=new Button{Text=text,Tag=key,Width=178,Height=42,FlatStyle=FlatStyle.Flat,BackColor=Panel,ForeColor=Muted,TextAlign=ContentAlignment.MiddleLeft,Padding=new Padding(12,0,0,0),Cursor=Cursors.Hand};
        b.FlatAppearance.BorderColor=Border; b.FlatAppearance.MouseOverBackColor=Color.FromArgb(28,28,28);
        b.Top=60+nav.Count*48; b.Left=0; b.Click+=(_,_)=>Navigate(key); sidebar.Controls.Add(b); nav[key]=b;
    }
    void Navigate(string key)
    {
        search.Visible=key=="commands"||key=="favorites";
        tiles.Visible=key=="commands"||key=="favorites";
        if(key=="commands"||key=="favorites"){title.Text=key=="commands"?"Команды":"Избранное"; ShowCommandTiles(key=="favorites");}
        else if(key=="reports") BuildReports();
        else if(key=="notes") BuildNotes();
        else if(key=="settings") BuildSettings();
        foreach(var x in nav.Values)x.ForeColor=Muted;
        if(nav.TryGetValue(key,out var active))active.ForeColor=Accent;
    }
    void ShowCommands(){Navigate("commands");}
    void ShowCommandTiles(bool favoritesOnly=false)
    {
        tiles.SuspendLayout(); tiles.Controls.Clear();
        var q=search.Text.Trim();
        var items=commands.Where(c=>c.Level<=config.Level && (!favoritesOnly||config.Favorites.Contains(c.Command)) &&
            (q.Length==0||c.Command.Contains(q,StringComparison.OrdinalIgnoreCase)||c.Category.Contains(q,StringComparison.OrdinalIgnoreCase)))
            .OrderBy(c=>c.Level).ThenBy(c=>c.Command);
        foreach(var c in items)
        {
            var tile=new Panel{Width=205,Height=92,BackColor=Panel,Margin=new Padding(0,0,12,12),Padding=new Padding(12)};
            var cmd=new Label{Text=c.Command,ForeColor=Accent,Font=new Font("Consolas",14,FontStyle.Bold),Dock=DockStyle.Top,Height=28};
            var meta=new Label{Text=$"Уровень {c.Level} · {c.Category}",ForeColor=Muted,Dock=DockStyle.Top,Height=22};
            var row=new FlowLayoutPanel{Dock=DockStyle.Bottom,Height=27,FlowDirection=FlowDirection.LeftToRight,WrapContents=false};
            var info=new Label{Text="?",Width=22,Height=23,TextAlign=ContentAlignment.MiddleCenter,ForeColor=Muted,BackColor=Color.FromArgb(32,32,32),Font=new Font("Segoe UI",8,FontStyle.Bold),Margin=new Padding(0,1,5,0),Cursor=Cursors.Help};
            info.Paint += (_,e) => { using var pen=new Pen(Border); e.Graphics.DrawEllipse(pen,2,2,17,17); };
            commandTip.SetToolTip(info, GetCommandDescription(c));
            info.MouseEnter += (_,_) => commandTip.Show(GetCommandDescription(c),info,info.Width/2,info.Height+4,12000);
            info.MouseLeave += (_,_) => commandTip.Hide(info);
            var bind=new Button{Text=config.Binds.GetValueOrDefault(c.Command,"Назначить"),Width=90,Height=25,FlatStyle=FlatStyle.Flat,ForeColor=TextMain,BackColor=Color.FromArgb(25,25,25)};
            bind.Click+=(_,_)=>CaptureBind(c.Command,bind);
            var fav=new Button{Text=config.Favorites.Contains(c.Command)?"★":"☆",Width=35,Height=25,FlatStyle=FlatStyle.Flat,ForeColor=Accent};
            fav.Click+=(_,_)=>{if(config.Favorites.Contains(c.Command))config.Favorites.Remove(c.Command);else config.Favorites.Add(c.Command);SaveConfig();ShowCommandTiles(favoritesOnly);};
            row.Controls.Add(info);row.Controls.Add(bind);row.Controls.Add(fav);
            tile.Controls.Add(row);tile.Controls.Add(meta);tile.Controls.Add(cmd);
            tile.DoubleClick+=(_,_)=>SendCommand(c.Command); cmd.DoubleClick+=(_,_)=>SendCommand(c.Command);
            tiles.Controls.Add(tile);
        }
        tiles.ResumeLayout();
    }
    void CaptureBind(string command,Button button)
    {
        // The bind prompt is an in-app overlay, never a separate Form/window.
        if (rootSurface == null) return;
        CloseBindOverlay();
        pendingBindCommand = command;
        pendingBindButton = button;

        bindOverlay = new Panel
        {
            Dock = DockStyle.Fill,
            BackColor = Color.FromArgb(245, 0, 0, 0),
            TabStop = true
        };
        var card = new Panel
        {
            Size = new Size(410, 174),
            BackColor = Color.FromArgb(20, 20, 20),
            BorderStyle = BorderStyle.FixedSingle,
            Anchor = AnchorStyles.None
        };
        bindOverlayText = new Label
        {
            Text = $"Назначение клавиши\n\n{command}\n\nНажмите любую клавишу",
            Dock = DockStyle.Fill,
            TextAlign = ContentAlignment.MiddleCenter,
            ForeColor = TextMain,
            Font = new Font("Segoe UI Semibold", 12)
        };
        var cancel = new Button
        {
            Text = "Отмена", Dock = DockStyle.Bottom, Height = 36,
            FlatStyle = FlatStyle.Flat, BackColor = Color.FromArgb(30, 30, 30),
            ForeColor = Muted, Cursor = Cursors.Hand
        };
        cancel.FlatAppearance.BorderColor = Border;
        cancel.Click += (_, _) => CloseBindOverlay();
        card.Controls.Add(bindOverlayText);
        card.Controls.Add(cancel);
        bindOverlay.Controls.Add(card);
        bindOverlay.Resize += (_, _) =>
        {
            card.Left = (bindOverlay.ClientSize.Width - card.Width) / 2;
            card.Top = (bindOverlay.ClientSize.Height - card.Height) / 2;
        };
        bindOverlay.KeyDown += HandleBindKeyDown;
        rootSurface.Controls.Add(bindOverlay);
        bindOverlay.BringToFront();
        card.Left = (bindOverlay.ClientSize.Width - card.Width) / 2;
        card.Top = (bindOverlay.ClientSize.Height - card.Height) / 2;

        // Keep keyboard capture on the main application form.
        Focus();
        ActiveControl = null;
    }

    void CloseBindOverlay()
    {
        if (bindOverlay != null)
        {
            if (rootSurface != null) rootSurface.Controls.Remove(bindOverlay);
            bindOverlay.Dispose();
        }
        bindOverlay = null;
        bindOverlayText = null;
        pendingBindCommand = null;
        pendingBindButton = null;
        Focus();
    }

    void HandleBindKeyDown(object? sender, KeyEventArgs e)
    {
        if (bindOverlay == null || pendingBindCommand == null) return;
        if (e.KeyCode == Keys.Escape)
        {
            CloseBindOverlay();
            e.SuppressKeyPress = true;
            return;
        }
        if (e.KeyCode is Keys.ControlKey or Keys.ShiftKey or Keys.Menu or Keys.LWin or Keys.RWin) return;

        var selected = e.KeyCode.ToString();
        foreach (var k in config.Binds.Where(x => x.Value == selected).Select(x => x.Key).ToList())
            config.Binds.Remove(k);
        config.Binds[pendingBindCommand] = selected;
        if (pendingBindButton != null && !pendingBindButton.IsDisposed)
            pendingBindButton.Text = selected;
        CloseBindOverlay();
        RegisterToggle();
        SaveConfig();
        e.SuppressKeyPress = true;
    }
    string GetCommandDescription(CommandItem c)
    {
        var known = new Dictionary<string,string>(StringComparer.OrdinalIgnoreCase)
        {
            ["/a"]="Отправить сообщение в административный чат.", ["/asms"]="Открыть список или инструменты администрации.",
            ["/admins"]="Показать список администрации онлайн.", ["/adelaction"]="Удалить административное действие.",
            ["/mute"]="Выдать игроку ограничение на чат.", ["/unmute"]="Снять ограничение на чат.",
            ["/offmute"]="Выдать офлайн-наказание за нарушение чата.", ["/offunmute"]="Снять офлайн-ограничение чата.",
            ["/fz"]="Заморозить персонажа игрока.", ["/unfz"]="Разморозить персонажа игрока.",
            ["/tp"]="Телепортироваться к игроку или указанной точке.", ["/tpc"]="Телепортироваться к автомобилю.",
            ["/tpcarnumber"]="Найти или переместиться к автомобилю по номеру.", ["/mypos"]="Показать текущие координаты персонажа.",
            ["/sp"]="Включить режим наблюдения.", ["/usp"]="Выйти из режима наблюдения.", ["/flip"]="Перевернуть транспортное средство.",
            ["/setdim"]="Изменить измерение персонажа.", ["/setdimcar"]="Изменить измерение автомобиля."
        };
        if (known.TryGetValue(c.Command, out var description)) return description;
        return c.Category.ToLowerInvariant() switch
        {
            "mute" => "Команда категории «Наказания чата». Используется для управления ограничениями чата.",
            "watch" => "Команда категории «Наблюдение и телепортация». Используется для контроля игрока или перемещения.",
            "chat" => "Команда категории «Чат». Используется для отправки сообщений или работы с чатами.",
            "custom" => "Пользовательская команда, добавленная в настройки.",
            _ => $"Команда {c.Command}. Категория: {c.Category}. Для точного описания проверьте справку сервера."
        };
    }
    async System.Threading.Tasks.Task CheckForUpdatesAsync()
    {
        if (!config.CheckUpdates) return;
        try
        {
            using var client = new HttpClient();
            client.DefaultRequestHeaders.UserAgent.ParseAdd("AdminPanel-Updater/1.0");
            client.Timeout = TimeSpan.FromSeconds(5);
            var json = await client.GetStringAsync("https://api.github.com/repos/Antropich/AdminPan/releases/latest");
            using var doc = JsonDocument.Parse(json);
            var tag = doc.RootElement.GetProperty("tag_name").GetString() ?? "";
            var url = doc.RootElement.GetProperty("html_url").GetString() ?? "https://github.com/Antropich/AdminPan/releases";
            var latestText = tag.TrimStart('v','V');
            var currentText = Application.ProductVersion;
            if (Version.TryParse(latestText, out var latest) && Version.TryParse(currentText, out var current) && latest > current && config.LastNotifiedVersion != tag)
            {
                config.LastNotifiedVersion = tag; SaveConfig();
                ShowUpdateToast(tag, url);
            }
        }
        catch { /* Проверка обновлений не должна мешать запуску приложения. */ }
    }
    void ShowUpdateToast(string version, string url)
    {
        updateToast?.Dispose();
        var toast = new Panel { Size = new Size(330, 104), BackColor = Color.FromArgb(22,22,22), BorderStyle = BorderStyle.FixedSingle, Anchor = AnchorStyles.Top | AnchorStyles.Right };
        var heading = new Label { Text = "Доступно обновление", Left = 14, Top = 10, Width = 295, Height = 24, ForeColor = Accent, Font = new Font("Segoe UI Semibold", 11) };
        var detail = new Label { Text = $"Новая версия {version} уже доступна", Left = 14, Top = 38, Width = 295, Height = 20, ForeColor = Muted };
        var open = new LinkLabel { Text = "Посмотреть обновление  →", Left = 14, Top = 67, Width = 200, Height = 22, LinkColor = Accent, ActiveLinkColor = TextMain };
        open.Click += (_,_) => Process.Start(new ProcessStartInfo(url) { UseShellExecute = true });
        var close = new Label { Text = "×", Left = 300, Top = 7, Width = 20, Height = 24, ForeColor = Muted, Cursor = Cursors.Hand, TextAlign = ContentAlignment.MiddleCenter };
        close.Click += (_,_) => { toastTimer?.Stop(); toast.Dispose(); updateToast = null; };
        toast.Controls.AddRange(new Control[] { heading, detail, open, close });
        Controls.Add(toast); updateToast = toast; PositionUpdateToast(); toast.BringToFront();
        toastTimer?.Dispose(); toastTimer = new System.Windows.Forms.Timer { Interval = 9000 };
        toastTimer.Tick += (_,_) => { toastTimer.Stop(); if (!toast.IsDisposed) toast.Dispose(); if (ReferenceEquals(updateToast,toast)) updateToast=null; };
        toastTimer.Start();
    }
    void PositionUpdateToast()
    {
        if (updateToast != null && !updateToast.IsDisposed)
        {
            updateToast.Left = ClientSize.Width - updateToast.Width - 18; updateToast.Top = 18;
        }
    }
    void RegisterToggle()
    {
        foreach (var id in registeredBinds.Keys.ToList()) UnregisterHotKey(Handle,id);
        registeredBinds.Clear();
        var all = new Dictionary<string,string>(config.Binds);
        all["act:toggle"] = all.GetValueOrDefault("act:toggle","Insert");
        int id = HOTKEY_ID;
        foreach (var pair in all)
        {
            if (!Enum.TryParse<Keys>(pair.Value,true,out var key) || key == Keys.None) continue;
            if (id == HOTKEY_ID || id > HOTKEY_ID)
            {
                if (RegisterHotKey(Handle,id,MOD_NOREPEAT,(uint)key))
                    registeredBinds[id] = pair.Key;
                id++;
            }
        }
    }
    protected override void WndProc(ref Message m)
    {
        if(m.Msg==WM_HOTKEY && registeredBinds.TryGetValue((int)m.WParam,out var action))
        {
            if((DateTime.Now-lastHotkey).TotalMilliseconds>config.CooldownMs)
            {
                lastHotkey=DateTime.Now;
                if(action=="act:toggle")
                {
                    compactMode=!compactMode;
                    ShowInTaskbar=!compactMode;
                    WindowState=compactMode?FormWindowState.Minimized:FormWindowState.Normal;
                }
                else if(!action.StartsWith("act:")) SendCommand(action);
            }
        }
        base.WndProc(ref m);
    }
    void SendCommand(string command)
    {
        try
        {
            if(config.AutoChat)
            {
                if(Enum.TryParse<Keys>(config.ChatKey,true,out var chat))SendKeys.SendWait("{"+chat+"}");
                System.Threading.Thread.Sleep(config.KeyDelayMs);
            }
            Clipboard.SetText(command);
            SendKeys.SendWait("^v");
        }
        catch(Exception ex){MessageBox.Show(this,"Не удалось отправить команду: "+ex.Message,"Admin Panel",MessageBoxButtons.OK,MessageBoxIcon.Warning);}
    }
    void ClearContent(){foreach(Control c in content.Controls.Cast<Control>().Where(c=>c!=title&&c!=search&&c!=tiles).ToList())content.Controls.Remove(c);}
    void BuildReports()
    {
        ClearContent();title.Text="Репорты";search.Visible=false;tiles.Visible=false;
        var count=new Label{Text="Отмечено сегодня: "+config.Reports.Count(x=>x.Date==DateTime.Today),Dock=DockStyle.Top,Height=60,ForeColor=Accent,Font=new Font("Segoe UI",18)};
        var add=new Button{Text="Добавить репорт",Dock=DockStyle.Top,Height=42};
        add.Click+=(_,_)=>{config.Reports.Add(DateTime.Now);SaveConfig();BuildReports();};content.Controls.Add(add);content.Controls.Add(count);
    }
    void BuildNotes()
    {
        ClearContent();title.Text="Заметки";search.Visible=false;tiles.Visible=false;
        var box=new TextBox{Multiline=true,ScrollBars=ScrollBars.Vertical,Dock=DockStyle.Fill,BackColor=Panel,ForeColor=TextMain,BorderStyle=BorderStyle.FixedSingle};
        box.Text=string.Join(Environment.NewLine,config.Notes);box.TextChanged+=(_,_)=>{config.Notes=box.Lines.ToList();SaveConfig();};content.Controls.Add(box);
    }
    void BuildSettings()
    {
        ClearContent();title.Text="Настройки";search.Visible=false;tiles.Visible=false;
        var panel=new FlowLayoutPanel{Dock=DockStyle.Fill,FlowDirection=FlowDirection.TopDown,WrapContents=false,AutoScroll=true};
        var level=new NumericUpDown{Minimum=1,Maximum=9,Value=config.Level,Width=180};
        level.ValueChanged+=(_,_)=>{config.Level=(int)level.Value;SaveConfig();};
        var chat=new TextBox{Text=config.ChatKey,Width=180};
        chat.TextChanged+=(_,_)=>{config.ChatKey=chat.Text;SaveConfig();};
        var delay=new NumericUpDown{Minimum=0,Maximum=2000,Value=config.KeyDelayMs,Width=180};
        delay.ValueChanged+=(_,_)=>{config.KeyDelayMs=(int)delay.Value;SaveConfig();};
        var auto=new CheckBox{Text="Автоматически открывать чат",Checked=config.AutoChat,ForeColor=TextMain,AutoSize=true};
        auto.CheckedChanged+=(_,_)=>{config.AutoChat=auto.Checked;SaveConfig();};
        panel.Controls.Add(MakeLabel("Уровень доступа"));panel.Controls.Add(level);
        panel.Controls.Add(MakeLabel("Клавиша чата"));panel.Controls.Add(chat);
        panel.Controls.Add(MakeLabel("Задержка (мс)"));panel.Controls.Add(delay);panel.Controls.Add(auto);
        content.Controls.Add(panel);
    }
    Label MakeLabel(string text)=>new(){Text=text,ForeColor=Muted,AutoSize=true,Margin=new Padding(0,12,0,4)};
    protected override void OnShown(EventArgs e){base.OnShown(e);Navigate("commands");}
}
