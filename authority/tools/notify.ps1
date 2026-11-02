param(
    [string]$Message = 'DSH 需要你的操作',
    [switch]$NoBeep
)

$ErrorActionPreference = 'Stop'

if (-not $NoBeep) {
    try { [System.Media.SystemSounds]::Asterisk.Play() } catch { }
}

Add-Type @'
using System;
using System.Runtime.InteropServices;

public static class DshFlash {
    [StructLayout(LayoutKind.Sequential)]
    public struct FLASHWINFO {
        public uint cbSize;
        public IntPtr hwnd;
        public uint dwFlags;
        public uint uCount;
        public uint dwTimeout;
    }

    [DllImport("user32.dll")]
    public static extern bool FlashWindowEx(ref FLASHWINFO pwfi);

    public static bool Flash(IntPtr hwnd) {
        if (hwnd == IntPtr.Zero) return false;
        var info = new FLASHWINFO();
        info.cbSize = (uint)Marshal.SizeOf(info);
        info.hwnd = hwnd;
        info.dwFlags = 0x2 | 0x4 | 0x8; // FLASHW_TRAY | FLASHW_TIMERNOFG | FLASHW_ALL
        info.uCount = 5;
        info.dwTimeout = 0;
        return FlashWindowEx(ref info);
    }
}
'@ -ErrorAction SilentlyContinue

$game = Get-Process isaac-ng -ErrorAction SilentlyContinue | Select-Object -First 1
if ($game -and $game.MainWindowHandle -ne 0) {
    [void][DshFlash]::Flash([IntPtr]$game.MainWindowHandle)
}

if (Get-Command New-BurntToastNotification -ErrorAction SilentlyContinue) {
    try { New-BurntToastNotification -Text 'DSH', $Message | Out-Null } catch { }
}

Write-Output $Message
