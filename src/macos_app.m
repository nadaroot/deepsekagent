// NonRoot - Native macOS Standalone Desktop Application (Cocoa + WebKit)
// Pure Cocoa + WebKit with zero external runtime dependencies.

#import <Cocoa/Cocoa.h>
#import <WebKit/WebKit.h>
#import <unistd.h>
#import <sys/socket.h>
#import <netinet/in.h>
#import <arpa/inet.h>

@interface AppDelegate : NSObject <NSApplicationDelegate, WKNavigationDelegate, WKUIDelegate, NSWindowDelegate, WKScriptMessageHandler>
@property (strong, nonatomic) NSWindow *window;
@property (strong, nonatomic) WKWebView *webView;
@property (strong, nonatomic) NSTask *pythonTask;
@property (strong, nonatomic) NSTask *proxyTask;
@property (assign, nonatomic) NSInteger serverPort;
@property (strong, nonatomic) NSString *serverURL;
@end

@implementation AppDelegate

- (void)applicationDidFinishLaunching:(NSNotification *)aNotification {
    [NSApp setActivationPolicy:NSApplicationActivationPolicyRegular];

    self.serverPort = 8765;
    self.serverURL = [NSString stringWithFormat:@"http://127.0.0.1:%ld", (long)self.serverPort];

    [self setupMenu];
    [self setupWindow];
    [self startOrConnectBackend];
}

- (void)setupMenu {
    NSMenu *mainMenu = [[NSMenu alloc] init];

    // 1. Application Menu
    NSMenuItem *appMenuItem = [[NSMenuItem alloc] init];
    NSMenu *appMenu = [[NSMenu alloc] initWithTitle:@"NonRoot"];
    
    [appMenu addItemWithTitle:@"О программе NonRoot" action:@selector(orderFrontStandardAboutPanel:) keyEquivalent:@""];
    [appMenu addItem:[NSMenuItem separatorItem]];
    [appMenu addItemWithTitle:@"Скрыть NonRoot" action:@selector(hide:) keyEquivalent:@"h"];
    
    NSMenuItem *hideOthers = [[NSMenuItem alloc] initWithTitle:@"Скрыть остальные" action:@selector(hideOtherApplications:) keyEquivalent:@"h"];
    [hideOthers setKeyEquivalentModifierMask:(NSEventModifierFlagCommand | NSEventModifierFlagOption)];
    [appMenu addItem:hideOthers];
    
    [appMenu addItemWithTitle:@"Показать все" action:@selector(unhideAllApplications:) keyEquivalent:@""];
    [appMenu addItem:[NSMenuItem separatorItem]];
    [appMenu addItemWithTitle:@"Завершить NonRoot" action:@selector(terminate:) keyEquivalent:@"q"];
    [appMenuItem setSubmenu:appMenu];
    [mainMenu addItem:appMenuItem];

    // 2. Edit Menu (Crucial for WKWebView standard keyboard shortcuts)
    NSMenuItem *editMenuItem = [[NSMenuItem alloc] init];
    NSMenu *editMenu = [[NSMenu alloc] initWithTitle:@"Правка"];
    [editMenu addItemWithTitle:@"Отменить" action:@selector(undo:) keyEquivalent:@"z"];
    
    NSMenuItem *redoItem = [[NSMenuItem alloc] initWithTitle:@"Повторить" action:@selector(redo:) keyEquivalent:@"Z"];
    [editMenu addItem:redoItem];
    [editMenu addItem:[NSMenuItem separatorItem]];
    
    [editMenu addItemWithTitle:@"Вырезать" action:@selector(cut:) keyEquivalent:@"x"];
    [editMenu addItemWithTitle:@"Скопировать" action:@selector(copy:) keyEquivalent:@"c"];
    [editMenu addItemWithTitle:@"Вставить" action:@selector(paste:) keyEquivalent:@"v"];
    [editMenu addItemWithTitle:@"Выбрать всё" action:@selector(selectAll:) keyEquivalent:@"a"];
    [editMenuItem setSubmenu:editMenu];
    [mainMenu addItem:editMenuItem];

    // 3. View Menu
    NSMenuItem *viewMenuItem = [[NSMenuItem alloc] init];
    NSMenu *viewMenu = [[NSMenu alloc] initWithTitle:@"Вид"];
    [viewMenu addItemWithTitle:@"Перезагрузить" action:@selector(reloadPage:) keyEquivalent:@"r"];
    [viewMenu addItemWithTitle:@"Во весь экран" action:@selector(toggleFullScreen:) keyEquivalent:@"f"];
    [viewMenuItem setSubmenu:viewMenu];
    [mainMenu addItem:viewMenuItem];

    // 4. Window Menu
    NSMenuItem *windowMenuItem = [[NSMenuItem alloc] init];
    NSMenu *windowMenu = [[NSMenu alloc] initWithTitle:@"Окно"];
    [windowMenu addItemWithTitle:@"Убрать в Dock" action:@selector(performMiniaturize:) keyEquivalent:@"m"];
    [windowMenu addItemWithTitle:@"Изменить масштаб" action:@selector(performZoom:) keyEquivalent:@""];
    [windowMenu addItem:[NSMenuItem separatorItem]];
    [windowMenu addItemWithTitle:@"Закрыть" action:@selector(performClose:) keyEquivalent:@"w"];
    [windowMenuItem setSubmenu:windowMenu];
    [mainMenu addItem:windowMenuItem];

    [NSApp setMainMenu:mainMenu];
}

- (void)setupWindow {
    NSRect frame = NSMakeRect(0, 0, 1280, 820);
    NSUInteger styleMask = NSWindowStyleMaskTitled |
                           NSWindowStyleMaskClosable |
                           NSWindowStyleMaskMiniaturizable |
                           NSWindowStyleMaskResizable |
                           NSWindowStyleMaskFullSizeContentView;

    self.window = [[NSWindow alloc] initWithContentRect:frame
                                              styleMask:styleMask
                                                backing:NSBackingStoreBuffered
                                                  defer:NO];

    self.window.title = @"NonRoot";
    self.window.minSize = NSMakeSize(920, 600);
    self.window.titleVisibility = NSWindowTitleHidden;
    self.window.titlebarAppearsTransparent = YES;
    self.window.backgroundColor = [NSColor colorWithRed:9.0/255.0 green:9.0/255.0 blue:11.0/255.0 alpha:1.0];
    self.window.appearance = [NSAppearance appearanceNamed:NSAppearanceNameDarkAqua];
    self.window.delegate = self;
    [self.window center];

    // Setup WebKit Configuration
    WKWebViewConfiguration *config = [[WKWebViewConfiguration alloc] init];
    [config.preferences setValue:@YES forKey:@"developerExtrasEnabled"];
    [config.preferences setValue:@YES forKey:@"fullScreenEnabled"];

    WKUserContentController *userContentController = [[WKUserContentController alloc] init];
    [userContentController addScriptMessageHandler:self name:@"nativePickFolder"];
    config.userContentController = userContentController;

    self.webView = [[WKWebView alloc] initWithFrame:self.window.contentView.bounds configuration:config];
    self.webView.autoresizingMask = NSViewWidthSizable | NSViewHeightSizable;
    self.webView.navigationDelegate = self;
    self.webView.UIDelegate = self;
    self.webView.wantsLayer = YES;
    self.webView.layer.backgroundColor = [NSColor colorWithRed:9.0/255.0 green:9.0/255.0 blue:11.0/255.0 alpha:1.0].CGColor;
    [self.webView setValue:@NO forKey:@"drawsBackground"];

    [self.window.contentView addSubview:self.webView];
    [self.window makeKeyAndOrderFront:nil];
    [NSApp activateIgnoringOtherApps:YES];
}

- (void)userContentController:(WKUserContentController *)userContentController didReceiveScriptMessage:(WKScriptMessage *)message {
    if ([message.name isEqualToString:@"nativePickFolder"]) {
        dispatch_async(dispatch_get_main_queue(), ^{
            [NSApp activateIgnoringOtherApps:YES];
            [self.window makeKeyAndOrderFront:nil];

            NSOpenPanel *panel = [NSOpenPanel openPanel];
            panel.canChooseFiles = NO;
            panel.canChooseDirectories = YES;
            panel.allowsMultipleSelection = NO;
            panel.canCreateDirectories = YES;
            panel.resolvesAliases = YES;
            panel.title = @"Выбрать папку проекта";
            panel.prompt = @"Выбрать";
            panel.message = @"Выберите рабочую папку проекта для NonRoot:";

            [panel beginSheetModalForWindow:self.window completionHandler:^(NSModalResponse returnCode) {
                if (returnCode == NSModalResponseOK) {
                    NSURL *url = [[panel URLs] firstObject];
                    if (url) {
                        NSString *path = [url path];
                        NSString *escaped = [[path stringByReplacingOccurrencesOfString:@"\\" withString:@"\\\\"] stringByReplacingOccurrencesOfString:@"\"" withString:@"\\\""];
                        NSString *js = [NSString stringWithFormat:@"if (window.onNativeFolderPicked) { window.onNativeFolderPicked(\"%@\"); }", escaped];
                        [self.webView evaluateJavaScript:js completionHandler:nil];
                    }
                }
            }];
        });
    }
}

- (void)reloadPage:(id)sender {
    if (self.webView) {
        [self.webView reload];
    }
}

- (BOOL)isPortOpen:(NSInteger)port {
    int sock = socket(AF_INET, SOCK_STREAM, 0);
    if (sock < 0) return NO;

    struct sockaddr_in serv_addr;
    memset(&serv_addr, 0, sizeof(serv_addr));
    serv_addr.sin_family = AF_INET;
    serv_addr.sin_port = htons(port);
    inet_pton(AF_INET, "127.0.0.1", &serv_addr.sin_addr);

    // Set 500ms timeout
    struct timeval tv;
    tv.tv_sec = 0;
    tv.tv_usec = 500000;
    setsockopt(sock, SOL_SOCKET, SO_RCVTIMEO, (const char*)&tv, sizeof tv);
    setsockopt(sock, SOL_SOCKET, SO_SNDTIMEO, (const char*)&tv, sizeof tv);

    int result = connect(sock, (struct sockaddr *)&serv_addr, sizeof(serv_addr));
    close(sock);
    return (result == 0);
}

- (NSString *)findPythonExecutable {
    NSArray *candidates = @[
        @"/usr/local/bin/python3",
        @"/opt/homebrew/bin/python3",
        @"/Library/Developer/CommandLineTools/usr/bin/python3",
        @"/usr/bin/python3"
    ];

    NSFileManager *fm = [NSFileManager defaultManager];
    for (NSString *cand in candidates) {
        if ([fm isExecutableFileAtPath:cand]) {
            return cand;
        }
    }
    return @"python3";
}

- (NSString *)findAppScript {
    NSString *bundlePath = [[NSBundle mainBundle] bundlePath];
    NSString *resScript = [bundlePath stringByAppendingPathComponent:@"Contents/Resources/app/nonroot.py"];
    if ([[NSFileManager defaultManager] fileExistsAtPath:resScript]) {
        return resScript;
    }

    NSString *home = NSHomeDirectory();
    NSString *userScript = [home stringByAppendingPathComponent:@".nonroot/app/nonroot.py"];
    if ([[NSFileManager defaultManager] fileExistsAtPath:userScript]) {
        return userScript;
    }

    return nil;
}

- (void)startProxyIfNeeded {
    if ([self isPortOpen:9655] || [self isPortOpen:3000]) {
        return;
    }

    NSString *bundlePath = [[NSBundle mainBundle] bundlePath];
    NSArray *proxyCandidates = @[
        [bundlePath stringByAppendingPathComponent:@"Contents/Resources/deepseek-api/server.js"],
        [NSHomeDirectory() stringByAppendingPathComponent:@".nonroot/deepseek-api/server.js"],
        @"/Users/mac/Documents/strim/playerok/deepseek-api/server.js"
    ];

    NSString *nodePath = nil;
    NSArray *nodeCandidates = @[@"/usr/local/bin/node", @"/opt/homebrew/bin/node", @"/usr/bin/node"];
    for (NSString *n in nodeCandidates) {
        if ([[NSFileManager defaultManager] isExecutableFileAtPath:n]) {
            nodePath = n;
            break;
        }
    }
    if (!nodePath) return;

    for (NSString *cand in proxyCandidates) {
        if ([[NSFileManager defaultManager] fileExistsAtPath:cand]) {
            self.proxyTask = [[NSTask alloc] init];
            self.proxyTask.launchPath = nodePath;
            self.proxyTask.currentDirectoryPath = [cand stringByDeletingLastPathComponent];
            self.proxyTask.arguments = @[cand];

            NSMutableDictionary *env = [NSMutableDictionary dictionaryWithDictionary:[[NSProcessInfo processInfo] environment]];
            env[@"NON_INTERACTIVE"] = @"1";
            env[@"PORT"] = @"9655";
            self.proxyTask.environment = env;

            NSString *logPath = [NSHomeDirectory() stringByAppendingPathComponent:@".nonroot/deepseek_proxy.log"];
            [[NSFileManager defaultManager] createFileAtPath:logPath contents:nil attributes:nil];
            NSFileHandle *handle = [NSFileHandle fileHandleForWritingAtPath:logPath];
            if (handle) {
                self.proxyTask.standardOutput = handle;
                self.proxyTask.standardError = handle;
            }

            @try {
                [self.proxyTask launch];
            } @catch (NSException *e) {
                NSLog(@"Failed to launch DeepSeek proxy: %@", e);
            }
            break;
        }
    }
}

- (void)startOrConnectBackend {
    [self startProxyIfNeeded];

    if ([self isPortOpen:self.serverPort]) {
        [self loadWebView];
        return;
    }

    NSString *pythonPath = [self findPythonExecutable];
    NSString *scriptPath = [self findAppScript];

    if (!scriptPath) {
        NSAlert *alert = [[NSAlert alloc] init];
        alert.messageText = @"Ошибка запуска NonRoot";
        alert.informativeText = @"Не найден основной скрипт nonroot.py в бандле приложения.";
        [alert runModal];
        return;
    }

    self.pythonTask = [[NSTask alloc] init];
    self.pythonTask.launchPath = pythonPath;
    self.pythonTask.arguments = @[
        scriptPath,
        @"--port", [NSString stringWithFormat:@"%ld", (long)self.serverPort],
        @"--no-browser"
    ];

    // Redirect logs to ~/.nonroot/app_backend.log
    NSString *logDir = [NSHomeDirectory() stringByAppendingPathComponent:@".nonroot"];
    [[NSFileManager defaultManager] createDirectoryAtPath:logDir withIntermediateDirectories:YES attributes:nil error:nil];
    NSString *logPath = [logDir stringByAppendingPathComponent:@"app_backend.log"];
    [[NSFileManager defaultManager] createFileAtPath:logPath contents:nil attributes:nil];
    NSFileHandle *logHandle = [NSFileHandle fileHandleForWritingAtPath:logPath];
    if (logHandle) {
        self.pythonTask.standardOutput = logHandle;
        self.pythonTask.standardError = logHandle;
    }

    @try {
        [self.pythonTask launch];
    } @catch (NSException *exception) {
        NSLog(@"Failed to launch Python backend: %@", exception);
    }

    // Poll until backend server becomes ready
    dispatch_async(dispatch_get_global_queue(DISPATCH_QUEUE_PRIORITY_DEFAULT, 0), ^{
        int maxAttempts = 50;
        BOOL ready = NO;
        for (int i = 0; i < maxAttempts; i++) {
            if ([self isPortOpen:self.serverPort]) {
                ready = YES;
                break;
            }
            usleep(100000); // 100ms
        }

        dispatch_async(dispatch_get_main_queue(), ^{
            if (ready) {
                [self loadWebView];
            } else {
                NSAlert *alert = [[NSAlert alloc] init];
                alert.messageText = @"Таймаут инициализации";
                alert.informativeText = @"Не удалось подключиться к серверу агента NonRoot.";
                [alert runModal];
            }
        });
    });
}

- (void)loadWebView {
    NSURL *url = [NSURL URLWithString:self.serverURL];
    NSURLRequest *req = [NSURLRequest requestWithURL:url cachePolicy:NSURLRequestReloadIgnoringLocalCacheData timeoutInterval:30.0];
    [self.webView loadRequest:req];
}

// WKNavigationDelegate
- (void)webView:(WKWebView *)webView didFinishNavigation:(WKNavigation *)navigation {
    [self.window makeKeyAndOrderFront:nil];
    [NSApp activateIgnoringOtherApps:YES];
}

// WKUIDelegate - Native Alert & Confirm dialog support
- (void)webView:(WKWebView *)webView runJavaScriptAlertPanelWithMessage:(NSString *)message initiatedByFrame:(WKFrameInfo *)frame completionHandler:(void (^)(void))completionHandler {
    NSAlert *alert = [[NSAlert alloc] init];
    alert.messageText = @"NonRoot";
    alert.informativeText = message;
    [alert addButtonWithTitle:@"ОК"];
    [alert beginSheetModalForWindow:self.window completionHandler:^(NSModalResponse returnCode) {
        completionHandler();
    }];
}

- (void)webView:(WKWebView *)webView runJavaScriptConfirmPanelWithMessage:(NSString *)message initiatedByFrame:(WKFrameInfo *)frame completionHandler:(void (^)(BOOL result))completionHandler {
    NSAlert *alert = [[NSAlert alloc] init];
    alert.messageText = @"Подтверждение";
    alert.informativeText = message;
    [alert addButtonWithTitle:@"Да"];
    [alert addButtonWithTitle:@"Отмена"];
    [alert beginSheetModalForWindow:self.window completionHandler:^(NSModalResponse returnCode) {
        completionHandler(returnCode == NSAlertFirstButtonReturn);
    }];
}

// NSApplicationDelegate
- (BOOL)applicationShouldHandleReopen:(NSApplication *)sender hasVisibleWindows:(BOOL)flag {
    if (!flag || !self.window.isVisible) {
        [self.window makeKeyAndOrderFront:nil];
    }
    if (self.window.isMiniaturized) {
        [self.window deminiaturize:nil];
    }
    [NSApp activateIgnoringOtherApps:YES];
    return YES;
}

- (BOOL)applicationShouldTerminateAfterLastWindowClosed:(NSApplication *)sender {
    return YES;
}

- (void)applicationWillTerminate:(NSNotification *)aNotification {
    if (self.pythonTask && [self.pythonTask isRunning]) {
        [self.pythonTask terminate];
    }
    if (self.proxyTask && [self.proxyTask isRunning]) {
        [self.proxyTask terminate];
    }
}

@end

int main(int argc, const char * argv[]) {
    @autoreleasepool {
        NSApplication *app = [NSApplication sharedApplication];
        AppDelegate *delegate = [[AppDelegate alloc] init];
        app.delegate = delegate;
        [app run];
    }
    return 0;
}
