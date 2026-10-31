#!/usr/bin/env python3
"""Isolated Qt Widgets palette/routing probe. Requires installed qt5ct/qt6ct.

Builds tiny native Qt5/Qt6 programs in temporary storage; never opens a window,
uses the live display/session bus/home, installs packages, or modifies settings.
Run only once the main integrator has installed the corresponding qtct plugins.
"""
import json
from datetime import datetime
import os
from pathlib import Path
import resource
import shlex
import shutil
import subprocess
import tempfile

from verify_native import expose_user_fonts

ROOT = Path(__file__).resolve().parent
SOURCE = r'''#include <QApplication>
#include <QPalette>
#include <QFont>
#include <QFontInfo>
#include <QFontDatabase>
#include <QTextLayout>
#include <QGlyphRun>
#include <QRawFont>
#include <QIcon>
#include <QProxyStyle>
#include <QStyle>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonArray>
#include <iostream>
int main(int argc, char **argv) {
    QApplication app(argc, argv);
    app.processEvents();
    QPalette p = app.palette();
    QStyle *style = app.style();
    auto *proxy = qobject_cast<QProxyStyle *>(style);
    const QFontInfo actualFont(app.font());
    const QFontInfo fixedFont(QFontDatabase::systemFont(QFontDatabase::FixedFont));
    auto usedFonts = [&](const QString &text) {
        QTextLayout layout(text, app.font());
        layout.beginLayout();
        layout.createLine();
        layout.endLayout();
        QJsonArray fonts;
        for (const QGlyphRun &run : layout.glyphRuns()) {
            bool missing = false;
            for (quint32 glyph : run.glyphIndexes())
                if (glyph == 0) missing = true;
            fonts.append(QJsonObject{{"family", run.rawFont().familyName()},
                                     {"style", run.rawFont().styleName()},
                                     {"missingGlyph", missing}});
        }
        return fonts;
    };
    QJsonObject result{
        {"qt", qVersion()},
        {"style", style->objectName()},
        {"baseStyle", proxy ? proxy->baseStyle()->objectName() : QString()},
        {"font", app.font().family()},
        {"actualFont", actualFont.family()},
        {"fontStyle", actualFont.styleName()},
        {"fontPointSize", app.font().pointSizeF()},
        {"resolvedPointSize", actualFont.pointSizeF()},
        {"fontRegular", actualFont.weight() == QFont::Normal},
        {"fixedFont", fixedFont.family()},
        {"koreanFonts", usedFonts(QString::fromUtf8("한글문서"))},
        {"latinFonts", usedFonts(QStringLiteral("Notes abc 123"))},
        {"iconTheme", QIcon::themeName()},
        {"folderIcon", !QIcon::fromTheme("folder").pixmap(32, 32).isNull()},
        {"fallbackIcon", !QIcon::fromTheme("document-open").pixmap(24, 24).isNull()},
        {"window", p.color(QPalette::Active, QPalette::Window).name()},
        {"text", p.color(QPalette::Active, QPalette::Text).name()},
        {"highlight", p.color(QPalette::Active, QPalette::Highlight).name()},
        {"highlightedText", p.color(QPalette::Active, QPalette::HighlightedText).name()}
    };
    std::cout << QJsonDocument(result).toJson(QJsonDocument::Compact).constData() << std::endl;
    return 0;
}
'''


def no_core():
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def run():
    palette = json.loads((ROOT / 'palette.json').read_text())
    output = ROOT / 'build'
    reports = []
    with tempfile.TemporaryDirectory(prefix='yuru-qt-routing-') as temporary:
        work = Path(temporary)
        home = work / 'home'
        config = home / '.config'
        runtime = work / 'runtime'
        runtime.mkdir(mode=0o700)
        source = work / 'probe.cpp'
        source.write_text(SOURCE)
        shutil.copytree(output / 'icons', home / '.local/share/icons')
        expose_user_fonts({'HOME': str(home)})
        for major in (5, 6):
            name = f'qt{major}ct'
            destination = config / name
            destination.mkdir(parents=True)
            for child in ('colors', 'qss'):
                shutil.copytree(output / name / child, destination / child)
            text = (output / name / (name + '.conf.fragment')).read_text()
            text = text.replace('/home/han/.config/', str(config) + '/')
            # Isolate platform-theme routing from Qt's QStyleSheetStyle wrapper.
            text = '\n'.join(line for line in text.splitlines() if not line.startswith('stylesheets=')) + '\n'
            (destination / (name + '.conf')).write_text(text)
            flags = subprocess.check_output(['pkg-config', '--cflags', '--libs', f'Qt{major}Widgets'], text=True)
            executable = work / ('probe-qt' + str(major))
            subprocess.run(['g++', '-std=c++17', '-fPIC', str(source), '-o', str(executable), *shlex.split(flags)],
                           check=True, timeout=45, preexec_fn=no_core)
            env = os.environ.copy()
            for key in ('DISPLAY', 'WAYLAND_DISPLAY', 'SWAYSOCK', 'QT_PLUGIN_PATH',
                        'QT_QPA_PLATFORM_PLUGIN_PATH', 'QT_STYLE_OVERRIDE', 'QT_QPA_GENERIC_PLUGINS'):
                env.pop(key, None)
            env.update({
                'HOME': str(home), 'XDG_CONFIG_HOME': str(config),
                'XDG_DATA_HOME': str(home / '.local/share'),
                'XDG_CACHE_HOME': str(home / '.cache'), 'XDG_STATE_HOME': str(home / '.local/state'),
                'XDG_RUNTIME_DIR': str(runtime),
                'DBUS_SESSION_BUS_ADDRESS': 'unix:path=' + str(work / 'no-session-bus'),
                'QT_QPA_PLATFORM': 'offscreen', 'QT_QPA_PLATFORMTHEME': 'qt5ct',
                'QT_ACCESSIBILITY': '0', 'QT_IM_MODULE': 'compose',
                'QT_OPENGL': 'software', 'LIBGL_ALWAYS_SOFTWARE': '1',
                'QT_QUICK_BACKEND': 'software', 'QSG_RHI_BACKEND': 'software',
                'QT_LOGGING_RULES': 'qt5ct.debug=true;qt6ct.debug=true;qt.qpa.theme.debug=true',
            })
            result = subprocess.run([str(executable)], env=env, capture_output=True,
                                    text=True, timeout=15, preexec_fn=no_core)
            if result.returncode:
                raise RuntimeError(f'Qt{major} probe failed: ' + result.stderr)
            report = json.loads(result.stdout.strip())
            for role, key in [('window', 'bg'), ('text', 'fg'), ('highlight', 'mint'), ('highlightedText', 'bg')]:
                assert report[role].lower() == palette[key].lower(), (major, role, report)
            assert report['style'].lower() == name + '-style', (major, report)
            assert report['baseStyle'].lower() == 'fusion', (major, report)
            assert report['font'] == report['actualFont'] == palette['browser_font'], (major, report)
            assert report['fontRegular'] and report['fontStyle'] == 'Regular', (major, report)
            assert report['fontPointSize'] == 10.5, (major, report)
            assert report['fixedFont'] == palette['font'], (major, report)
            for key, family in [('koreanFonts', palette['fallback_font']),
                                ('latinFonts', palette['font'])]:
                assert report[key] and all(face['family'] == family and not face['missingGlyph']
                                           for face in report[key]), (major, key, report)
            assert report['iconTheme'] == 'Yuru', (major, report)
            assert report['folderIcon'] and report['fallbackIcon'], (major, report)
            restarted = subprocess.run([str(executable)], env=env, capture_output=True,
                                       text=True, check=True, timeout=15, preexec_fn=no_core)
            assert json.loads(restarted.stdout.strip()) == report, (major, restarted.stdout)
            reports.append({'major': major, 'fresh_starts': 2, 'result': report})
            print(json.dumps({'major': major, 'sharedKey': 'qt5ct', 'result': report}, ensure_ascii=False))
            print(result.stderr.strip())
    (ROOT / 'verification/icons-qt.json').write_text(json.dumps({
        'checked_at': datetime.now().astimezone().isoformat(timespec='seconds'),
        'scope': 'Isolated offscreen Qt5/6 processes; live apps and desktop were not restarted.',
        'probes': reports,
    }, indent=2) + '\n')


if __name__ == '__main__':
    run()
