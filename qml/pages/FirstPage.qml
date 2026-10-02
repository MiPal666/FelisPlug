import QtQuick 2.0
import Sailfish.Silica 1.0
import io.thp.pyotherside 1.5

Page {
    id: page

    property var appWindowRef

    allowedOrientations: Orientation.All

    property string viewState: "loading"
    property bool busy: true
    property string errorText: ""

    function updateCoverCounts(onCount, offCount, unavailableCount, totalCount) {
        if (!appWindowRef)
            return

        appWindowRef.coverOnCount = onCount
        appWindowRef.coverOffCount = offCount
        appWindowRef.coverUnavailableCount = unavailableCount
        appWindowRef.coverPlugCount = totalCount
    }

    function replacePlugs(plugs) {
        var onCount = 0
        var offCount = 0
        var unavailableCount = 0

        plugModel.clear()
        if (!plugs) {
            updateCoverCounts(0, 0, 0, 0)
            return
        }

        for (var i = 0; i < plugs.length; ++i) {
            var isOn = plugs[i].is_on === true
            var isAvailable = plugs[i].online !== false

            if (!isAvailable)
                unavailableCount += 1
            else if (isOn)
                onCount += 1
            else
                offCount += 1

            plugModel.append({
                "plugName": plugs[i].name,
                "serial": plugs[i].serial,
                "isOn": isOn,
                "isAvailable": isAvailable,
                "groupId": plugs[i].group_id === undefined ? null : plugs[i].group_id
            })
        }

        updateCoverCounts(onCount, offCount, unavailableCount, plugs.length)
    }


    function formatBackendError(result) {
        var code = parseInt(result.error_code)
        var hasCode = !isNaN(code)
        if (code === 1226 || code === 1013 || code === 1014)
            return qsTr("Incorrect account or password.")
        if (code === 1011 || code === 1012)
            return qsTr("Incorrect verification code.")
        if (code === 1015)
            return qsTr("EZVIZ account is locked.")
        if (result.error_kind === "device_unavailable" || code === 2003 || code === 2009) {
            var name = result.device_name || result.serial || qsTr("Device")
            if (hasCode)
                return qsTr('Device "%1" is unavailable. Reconnect it and refresh the list. (EZVIZ %2)').arg(name).arg(code)
            return qsTr('Device "%1" is unavailable. Reconnect it and refresh the list.').arg(name)
        }
        if (hasCode)
            return qsTr("EZVIZ service error (code %1).").arg(code)
        return result.error || qsTr("Unknown error")
    }

    function applyResult(result) {
        busy = false

        if (!result) {
            errorText = qsTr("Empty response from backend")
            return
        }

        if (result.account !== undefined && result.account !== "")
            accountField.text = result.account

        if (result.plugs !== undefined)
            replacePlugs(result.plugs)

        if (result.status === "ok") {
            errorText = ""
            accountField.focus = false
            passwordField.focus = false
            mfaField.focus = false
            Qt.inputMethod.hide()
            passwordField.text = ""
            mfaField.text = ""
            viewState = "plugs"
        } else if (result.status === "mfa_required") {
            errorText = result.message || qsTr("Verification code sent")
            passwordField.text = ""
            viewState = "mfa"
        } else if (result.status === "login_required") {
            errorText = ""
            passwordField.text = ""
            mfaField.text = ""
            replacePlugs([])
            viewState = "login"
        } else {
            errorText = formatBackendError(result)
            if (viewState === "loading")
                viewState = "login"
        }
    }

    function backendCall(name, args) {
        busy = true
        python.call(name, args || [], function(result) {
            applyResult(result)
        })
    }

    ListModel {
        id: plugModel
    }

    Python {
        id: python

        Component.onCompleted: {
            addImportPath(Qt.resolvedUrl("../python"))
            importModule("felisplug_backend", function() {
                page.backendCall("felisplug_backend.initialize", [])
            })
        }

        onError: {
            busy = false
            errorText = traceback
            if (viewState === "loading")
                viewState = "login"
            console.log("Python error: " + traceback)
        }
    }

    SilicaFlickable {
        id: loginView
        anchors.fill: parent
        visible: viewState === "login" || viewState === "mfa"
        contentHeight: loginColumn.height + Theme.paddingLarge

        VerticalScrollDecorator {}

        Column {
            id: loginColumn
            width: parent.width
            spacing: Theme.paddingMedium

            PageHeader {
                title: qsTr("Felis Plug for EZVIZ")
            }

            Label {
                width: parent.width - 2 * Theme.horizontalPageMargin
                x: Theme.horizontalPageMargin
                wrapMode: Text.Wrap
                color: Theme.secondaryColor
                text: viewState === "mfa"
                      ? qsTr("Enter the verification code sent by EZVIZ.")
                      : qsTr("Sign in to your EZVIZ account.")
            }

            TextField {
                id: accountField
                width: parent.width
                visible: viewState === "login"
                enabled: !busy
                label: qsTr("Email or account")
                placeholderText: qsTr("Email or account")
                inputMethodHints: Qt.ImhNoAutoUppercase | Qt.ImhNoPredictiveText
            }

            TextField {
                id: passwordField
                width: parent.width
                visible: viewState === "login"
                enabled: !busy
                label: qsTr("Password")
                placeholderText: qsTr("Password")
                echoMode: TextInput.Password
                inputMethodHints: Qt.ImhNoPredictiveText
                EnterKey.enabled: text.length > 0 && accountField.text.length > 0
                EnterKey.iconSource: "image://theme/icon-m-enter-accept"
                EnterKey.onClicked: signInButton.clicked()
            }

            Button {
                id: signInButton
                anchors.horizontalCenter: parent.horizontalCenter
                visible: viewState === "login"
                enabled: !busy && accountField.text.length > 0 && passwordField.text.length > 0
                text: qsTr("Sign in")
                onClicked: page.backendCall(
                    "felisplug_backend.login",
                    [accountField.text, passwordField.text]
                )
            }

            TextField {
                id: mfaField
                width: parent.width
                visible: viewState === "mfa"
                enabled: !busy
                label: qsTr("Verification code")
                placeholderText: qsTr("Verification code")
                inputMethodHints: Qt.ImhDigitsOnly
                EnterKey.enabled: text.length > 0
                EnterKey.iconSource: "image://theme/icon-m-enter-accept"
                EnterKey.onClicked: verifyButton.clicked()
            }

            Button {
                id: verifyButton
                anchors.horizontalCenter: parent.horizontalCenter
                visible: viewState === "mfa"
                enabled: !busy && mfaField.text.length > 0
                text: qsTr("Verify")
                onClicked: page.backendCall(
                    "felisplug_backend.submit_mfa",
                    [mfaField.text]
                )
            }

            Button {
                anchors.horizontalCenter: parent.horizontalCenter
                visible: viewState === "mfa"
                enabled: !busy
                text: qsTr("Back to sign in")
                onClicked: {
                    errorText = ""
                    mfaField.text = ""
                    viewState = "login"
                }
            }

            Label {
                width: parent.width - 2 * Theme.horizontalPageMargin
                x: Theme.horizontalPageMargin
                visible: errorText.length > 0
                wrapMode: Text.Wrap
                color: Theme.highlightColor
                text: errorText
            }

            Label {
                width: parent.width - 2 * Theme.horizontalPageMargin
                x: Theme.horizontalPageMargin
                visible: viewState === "login"
                wrapMode: Text.Wrap
                color: Theme.secondaryColor
                font.pixelSize: Theme.fontSizeSmall
                text: qsTr("Your password is used only for authentication and is not stored. The EZVIZ session token is stored locally.")
            }
        }
    }

    SilicaListView {
        id: listView
        anchors.fill: parent
        visible: viewState === "plugs"
        model: plugModel

        PullDownMenu {
            MenuItem {
                text: qsTr("About")
                onClicked: pageStack.push(Qt.resolvedUrl("AboutPage.qml"), {
                    "appVersion": appWindowRef ? appWindowRef.appVersion : "0.1.0"
                })
            }
            MenuItem {
                text: qsTr("Logout")
                enabled: !busy
                onClicked: page.backendCall("felisplug_backend.logout", [])
            }
            MenuItem {
                text: qsTr("Refresh")
                enabled: !busy
                onClicked: page.backendCall("felisplug_backend.refresh", [])
            }
        }

        header: Column {
            width: listView.width

            PageHeader {
                title: qsTr("Felis Plug for EZVIZ")
            }

            Label {
                width: parent.width - 2 * Theme.horizontalPageMargin
                x: Theme.horizontalPageMargin
                visible: errorText.length > 0
                wrapMode: Text.Wrap
                color: Theme.highlightColor
                text: errorText
            }
        }

        delegate: BackgroundItem {
            id: plugItem
            width: listView.width
            height: Theme.itemSizeMedium

            Column {
                anchors {
                    left: parent.left
                    leftMargin: Theme.horizontalPageMargin
                    right: powerSwitch.left
                    rightMargin: Theme.paddingMedium
                    verticalCenter: parent.verticalCenter
                }
                spacing: 0

                Label {
                    width: parent.width
                    text: plugName
                    truncationMode: TruncationMode.Fade
                    color: isAvailable
                           ? (plugItem.highlighted ? Theme.highlightColor : Theme.primaryColor)
                           : Theme.secondaryColor
                }

                Label {
                    width: parent.width
                    visible: !isAvailable
                    text: qsTr("Unavailable")
                    color: Theme.highlightColor
                    font.pixelSize: Theme.fontSizeSmall
                }
            }

            Switch {
                id: powerSwitch
                anchors {
                    right: parent.right
                    rightMargin: Theme.horizontalPageMargin
                    verticalCenter: parent.verticalCenter
                }
                checked: isOn
                enabled: !busy && isAvailable
                opacity: isAvailable ? 1.0 : 0.30

                onClicked: page.backendCall(
                    "felisplug_backend.set_plug",
                    [serial, checked, plugName]
                )
            }
        }


        ViewPlaceholder {
            enabled: !busy && plugModel.count === 0
            text: qsTr("No EZVIZ smart plugs found")
            hintText: qsTr("Pull down to refresh")
        }
    }

    BusyIndicator {
        anchors.centerIn: parent
        running: busy
        size: BusyIndicatorSize.Large
    }
}
