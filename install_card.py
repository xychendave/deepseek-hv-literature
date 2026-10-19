"""Build a private local Harness bundle and install it using the official CLI."""
import json
import os
from pathlib import Path
import shutil
import subprocess

from hv_literature import atomic_write

PACKAGE = "@xychendave/dsh-hv-literature"
BEGIN = "# BEGIN hv-literature managed block"
END = "# END hv-literature managed block"


def remove_legacy_block(content):
    """Remove only our old direct MCP registration, keeping other settings."""
    if BEGIN not in content and END not in content:
        return content
    if content.count(BEGIN) != 1 or content.count(END) != 1:
        raise ValueError("旧文献插件托管块不完整；未修改配置")
    first, last = content.index(BEGIN), content.index(END)
    if last < first:
        raise ValueError("旧文献插件托管块顺序错误；未修改配置")
    remainder = (content[:first] + content[last+len(END):]).strip()
    # A valid empty YAML list, instead of null, is required by Harness.
    if not any(line.strip() and not line.lstrip().startswith("#") for line in remainder.splitlines()):
        remainder = (remainder+"\n" if remainder else "") + "[]"
    return remainder + "\n"


def build_bundle(root):
    root = Path(root).resolve()
    source = root / "harness-card"
    target = root / "data/harness-plugin"
    # Copy an allowlist only: no papers, local config, credentials or database.
    for relative in ["package.json", "index.js", "icon.svg", "locale/en.json", "locale/zh.json"]:
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(destination, (source/relative).read_text(encoding="utf-8"))
    row = {"id":"hv-research-mcp", "name":"@deepseek-ai/dsh-mcp-client", "config":{
        "transport":"stdio", "serverName":"hv_research", "command":str(root/"hv-literature"),
        "args":["mcp"], "cwd":str(root), "env":{}, "toolCallTimeoutMs":600000,
        "failOnStartupError":False}}
    # JSON is valid YAML, and preserves spaces/non-ASCII paths without quoting errors.
    atomic_write(target/"cordis.patch.yml", json.dumps([{"insert":[row]}], ensure_ascii=False, indent=2)+"\n")
    return target


def install_card(root, dsh_home, profiles, skill_dirs, dry_run=False, dsh_command="dsh"):
    import datetime
    root = Path(root).resolve()
    home = Path(dsh_home).expanduser().resolve()
    template = json.loads((root/"harness-card/package.json").read_text(encoding="utf-8"))
    if template["name"] != PACKAGE:
        raise ValueError("插件包标识不匹配")
    skill = root/"skill/hv-literature"
    links = [Path(p).expanduser().resolve()/"hv-literature" for p in dict.fromkeys(skill_dirs)]
    for link in links:
        if (link.exists() or link.is_symlink()) and link.resolve() != skill.resolve():
            raise ValueError(f"存在其他同名 Skill，未修改配置：{link}")
    plans = []
    for profile in dict.fromkeys(profiles):
        if Path(profile).name != profile or profile in (".", ".."):
            raise ValueError("profile 必须是单个目录名")
        directory = home/"profiles"/profile
        if not (directory/"package.json").is_file():
            raise ValueError(f"未找到 Harness profile，请先启动客户端并确认 --dsh-home：{directory}")
        manifest = json.loads((directory/"package.json").read_text(encoding="utf-8"))
        patch = directory/"cordis.patch.yml"
        before = patch.read_text(encoding="utf-8") if patch.exists() else "[]\n"
        after = remove_legacy_block(before)
        plans.append((profile, directory, manifest, patch, before, after))
    if not plans:
        raise ValueError("至少指定一个 profile")
    bundle = root/"data/harness-plugin"
    result = {"dry_run":dry_run, "package":PACKAGE, "bundle":str(bundle), "dsh_home":str(home),
              "profiles":[], "skill_links":[str(x) for x in links]}
    if dry_run:
        result["profiles"] = [{"profile":p, "migrate_legacy":before != after} for p,_,_,_,before,after in plans]
        return result
    executable = shutil.which(dsh_command)
    if not executable:
        raise RuntimeError("找不到 dsh；请安装官方 Harness CLI，或用 --dsh-command 指定其绝对路径")
    bundle = build_bundle(root)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    for profile, directory, manifest, patch, before, after in plans:
        record = {"profile":profile, "config":str(patch), "migrated_legacy":before != after}
        if before != after:
            backup = patch.with_name(patch.name+".before-hv-card-"+stamp)
            shutil.copy2(patch, backup)
            record["backup"] = str(backup)
            atomic_write(patch, after)
            shutil.copymode(backup, patch)
        installed = directory/"node_modules"/PACKAGE
        is_same = PACKAGE in manifest.get("dependencies", {}) and installed.exists() and installed.resolve() == bundle.resolve()
        if not is_same:
            command = [executable, "plugin", "--profile", profile, "add", "link:"+str(bundle)]
            try:
                proc = subprocess.run(command, cwd=root, env={**os.environ, "DSH_HOME":str(home)},
                                      capture_output=True, text=True, timeout=180)
            except (subprocess.TimeoutExpired, OSError):
                if before != after:
                    atomic_write(patch, before)
                    shutil.copymode(backup, patch)
                raise RuntimeError(f"Harness 安装超时或无法启动，旧 MCP 配置已恢复（{profile}）") from None
            if proc.returncode:
                # Restore our previous registration when official installation fails.
                if before != after:
                    atomic_write(patch, before)
                    shutil.copymode(backup, patch)
                raise RuntimeError(f"Harness 安装失败，旧 MCP 配置已恢复（{profile}）。\n"+(proc.stderr or proc.stdout)[-2500:])
        current = json.loads((directory/"package.json").read_text(encoding="utf-8"))
        if PACKAGE not in current.get("dependencies", {}) or not installed.exists():
            raise RuntimeError(f"安装命令完成但未找到插件登记：{directory}")
        record["enabled"] = PACKAGE in current.get("dsh", {}).get("profile", {}).get("bundles", [])
        record["already_installed"] = is_same
        result["profiles"].append(record)
    for link in links:
        link.parent.mkdir(parents=True, exist_ok=True)
        if not link.is_symlink():
            link.symlink_to(skill, target_is_directory=True)
    result["installed_at"] = stamp
    atomic_write(root/"data/card-installation.json", json.dumps(result, ensure_ascii=False, indent=2)+"\n")
    return result
