# Source after both qt5ct and qt6ct are installed and verified.
# qt6ct advertises qt5ct as a compatibility key; each Qt major searches its own
# plugin directory and reads its own qt5ct/qt6ct configuration directory.
# QT_QPA_PLATFORMTHEME is ONE key, not a semicolon/colon fallback list.
export QT_QPA_PLATFORMTHEME=qt5ct
