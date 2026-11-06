using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;
using System.Text.Json;
using System.Text.Json.Serialization;
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
    readonly Label title = new();
    readonly TextBox search = new();
    readonly FlowLayoutPanel tiles = new();
    readonly Dictionary<string,Button> nav = new();
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
        BackColor=Bg; ForeColor=TextMain; Font=new Font("Segoe UI",9.5f);
        FormBorderStyle=FormBorderStyle.Sizable; StartPosition=FormStartPosition.CenterScreen;
        BuildShell(); ShowCommands(); RegisterToggle();
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
        var root=new Panel{Dock=DockStyle.Fill,BackColor=Bg,Padding=new Padding(12)}; Controls.Add(root);
        sidebar.Width=205; sidebar.Dock=DockStyle.Left; sidebar.BackColor=Panel; sidebar.Padding=new Padding(12);
        root.Controls.Add(sidebar);
        var brand=new Label{Text="ADMIN PANEL",Dock=DockStyle.Top,Height=52,ForeColor=Accent,Font=new Font("Segoe UI Semibold",13),TextAlign=ContentAlignment.MiddleLeft};
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
            var row=new FlowLayoutPanel{Dock=DockStyle.Bottom,Height=27,FlowDirection=FlowDirection.LeftToRight};
            var bind=new Button{Text=config.Binds.GetValueOrDefault(c.Command,"Назначить"),Width=90,Height=25,FlatStyle=FlatStyle.Flat,ForeColor=TextMain,BackColor=Color.FromArgb(25,25,25)};
            bind.Click+=(_,_)=>CaptureBind(c.Command,bind);
            var fav=new Button{Text=config.Favorites.Contains(c.Command)?"★":"☆",Width=35,Height=25,FlatStyle=FlatStyle.Flat,ForeColor=Accent};
            fav.Click+=(_,_)=>{if(config.Favorites.Contains(c.Command))config.Favorites.Remove(c.Command);else config.Favorites.Add(c.Command);SaveConfig();ShowCommandTiles(favoritesOnly);};
            row.Controls.Add(bind);row.Controls.Add(fav);
            tile.Controls.Add(row);tile.Controls.Add(meta);tile.Controls.Add(cmd);
            tile.DoubleClick+=(_,_)=>SendCommand(c.Command); cmd.DoubleClick+=(_,_)=>SendCommand(c.Command);
            tiles.Controls.Add(tile);
        }
        tiles.ResumeLayout();
    }
    void CaptureBind(string command,Button button)
    {
        using var d=new KeyCaptureDialog(); if(d.ShowDialog(this)==DialogResult.OK && !string.IsNullOrWhiteSpace(d.SelectedKey))
        {
            foreach(var k in config.Binds.Where(x=>x.Value==d.SelectedKey).Select(x=>x.Key).ToList())config.Binds.Remove(k);
            config.Binds[command]=d.SelectedKey; button.Text=d.SelectedKey; RegisterToggle(); SaveConfig();
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
public sealed class KeyCaptureDialog : Form
{
    public string SelectedKey="";
    Label prompt=new(){Text="Нажмите клавишу для назначения",Dock=DockStyle.Fill,TextAlign=ContentAlignment.MiddleCenter,ForeColor=Color.White};
    public KeyCaptureDialog(){Text="Назначить клавишу";Size=new Size(360,150);BackColor=Color.FromArgb(15,15,15);FormBorderStyle=FormBorderStyle.FixedDialog;StartPosition=FormStartPosition.CenterParent;Controls.Add(prompt);KeyPreview=true;KeyDown+=(_,e)=>{SelectedKey=e.KeyCode.ToString();DialogResult=DialogResult.OK;Close();};}
}
