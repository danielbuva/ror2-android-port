/* Small local Windows compiler driver; no shader implementation is included. */
typedef unsigned long U32;
typedef unsigned long long Size;
typedef unsigned short Wide;
typedef void *Handle;
__declspec(dllimport) Wide *GetCommandLineW(void);
__declspec(dllimport) Wide **CommandLineToArgvW(const Wide *, int *);
__declspec(dllimport) Handle CreateFileW(const Wide *, U32, U32, void *, U32, U32, Handle);
__declspec(dllimport) U32 GetFileSize(Handle, U32 *);
__declspec(dllimport) int ReadFile(Handle, void *, U32, U32 *, void *);
__declspec(dllimport) int WriteFile(Handle, const void *, U32, U32 *, void *);
__declspec(dllimport) int CloseHandle(Handle);
__declspec(dllimport) Handle GetProcessHeap(void);
__declspec(dllimport) void *HeapAlloc(Handle, U32, Size);
__declspec(dllimport) Handle LoadLibraryA(const char *);
__declspec(dllimport) void *GetProcAddress(Handle, const char *);
__declspec(dllimport) Handle GetStdHandle(U32);
__declspec(dllimport) void ExitProcess(U32);
typedef struct {void **vtable;} Blob;
typedef long (*Compile)(const void *, Size, const char *, const void *, void *, const char *, const char *, U32, U32, Blob **, Blob **);
static void *bytes(Blob *b) {return ((void *(*)(Blob *))b->vtable[3])(b);}
static Size length(Blob *b) {return ((Size (*)(Blob *))b->vtable[4])(b);}
static void message(const char *p, U32 size) {U32 written;WriteFile(GetStdHandle((U32)-11),p,size,&written,0);}
void main(void) {
    int count=0;Wide **args=CommandLineToArgvW(GetCommandLineW(),&count);
    if(count!=4) {message("Usage: validator source profile output\n",39);ExitProcess(2);}
    Handle input=CreateFileW(args[1],0x80000000,1,0,3,0,0);
    if(input==(Handle)-1) {message("Input open failed\n",18);ExitProcess(3);}
    U32 size=GetFileSize(input,0),read=0;
    if(size==0||size>16*1024*1024) ExitProcess(4);
    void *source=HeapAlloc(GetProcessHeap(),0,size);
    if(!source||!ReadFile(input,source,size,&read,0)||read!=size) ExitProcess(5);
    CloseHandle(input);
    char profile[32];int i=0;
    while(args[2][i]&&i<31) {if(args[2][i]>127) ExitProcess(6);profile[i]=(char)args[2][i];i++;}profile[i]=0;
    Handle dll=LoadLibraryA("d3dcompiler_46.dll");
    Compile compile=dll?(Compile)GetProcAddress(dll,"D3DCompile"):0;
    if(!compile) {message("D3DCompile unavailable\n",23);ExitProcess(7);}
    Blob *code=0,*errors=0;
    long result=compile(source,size,"local-validation",0,0,"main",profile,1<<11,0,&code,&errors);
    if(errors) message((const char *)bytes(errors),(U32)length(errors));
    if(result<0||!code) ExitProcess(8);
    Handle output=CreateFileW(args[3],0x40000000,0,0,2,0,0);U32 written=0;
    if(output==(Handle)-1||length(code)>16*1024*1024||!WriteFile(output,bytes(code),(U32)length(code),&written,0)||written!=length(code)) ExitProcess(9);
    CloseHandle(output);message("HLSL compilation passed\n",24);ExitProcess(0);
}
