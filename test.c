/* main.c */
#include <stdio.h>

extern int llvm(); 

int main() {
    printf("llvm() returned %i\n", llvm(6));
}
