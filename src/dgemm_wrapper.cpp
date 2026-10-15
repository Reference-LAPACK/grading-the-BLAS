#include "dgemm_wrapper.hpp"
#include "utils.hpp"
#include <cmath>

#if defined(USE_CUDA)
#include <cuda_runtime.h>
#include <cublas_v2.h>
#endif

extern "C" {
    void dgemm_(const char* TRANSA, const char* TRANSB,
                const int* M, const int* N, const int* K,
                const double* ALPHA,
                const double* A, const int* LDA,
                const double* B, const int* LDB,
                const double* BETA,
                double* C, const int* LDC);
}

void dgemm_wrapper( const char transa, const char transb,
                    const int m, const int n, const int k,
                    const double alpha,
                    double *A, const int lda,
                    double *B, const int ldb,
                    const double beta,
                    double *C, const int ldc ){

#if defined(USE_CUDA)
    cublasHandle_t handle;
    cublasCreate(&handle);
        
#if CUBLAS_VERSION >= 130100
    // ask cuBLAS to report the mantissa bit count its FP64 emulation guard chose for this call;
    // it stays -1 when no emulated path was considered (emulation off, or a native-only call)
    int *emulation_bits;
    cudaHostAlloc((void**)&emulation_bits, sizeof(int), cudaHostAllocDefault);
    *emulation_bits = -1;
    cublasSetFixedPointEmulationMantissaBitCountPointer(handle, emulation_bits);
#endif

    cublasOperation_t opA = CUBLAS_OP_N;
    cublasOperation_t opB = CUBLAS_OP_N;

    double *d_A, *d_B, *d_C;
#endif

#if defined(INNER_SCALING) || defined(OUTER_SCALING)
    // save prescaled A and B for restoring after the DGEMM
    std::vector<double> A_prescaled(lda * k);
    std::vector<double> B_prescaled(ldb * n);
    copy_matrix(m, k, &A_prescaled[0], lda, A, lda);
    copy_matrix(k, n, &B_prescaled[0], ldb, B, ldb);
#endif

#if defined(INNER_SCALING)

    std::vector<double> A_col_norms(k);
    std::vector<double> B_row_norms(k);

    // find inf norms of cols of A
    for ( int i = 0; i < k; ++i ){
        A_col_norms[i] = std::abs(A[0 + i * lda]);
        for ( int j = 1; j < m; ++j ){
            A_col_norms[i] = std::abs(A[j + i*lda]) > A_col_norms[i] ? std::abs(A[j + i*lda]) : A_col_norms[i];
        }
    }

    // find inf norms of rows of B
    for ( int i = 0; i < k; ++i ){
        B_row_norms[i] = std::abs(B[i + 0 * ldb]);
        for ( int j = 1; j < n; ++j ){
            B_row_norms[i] = std::abs(B[i + j*ldb]) > B_row_norms[i] ? std::abs(B[i + j*ldb]) : B_row_norms[i];
        }
    }

    // scaling to yield roughly equivalent col/row norms
    for ( int i = 0; i < k; ++i ){
        double scaling_factor = A_col_norms[i] * B_row_norms[i] != 0 ? std::ldexp(1.0, std::round((std::log2(B_row_norms[i]) - std::log2(A_col_norms[i])) / 2.0)) : 1.0;        
        for ( int j = 0; j < m; ++j ){
            A[j + i*lda] = A[j + i*lda] * scaling_factor;
        }
        for ( int j = 0; j < n; ++j ){
            B[i + j*ldb] = B[i + j*ldb] / scaling_factor;
        }
    }

#elif defined(OUTER_SCALING)

    std::vector<double> A_row_norms(m);
    std::vector<double> B_col_norms(n);

    // find inf norms of rows of A
    for ( int i = 0; i < m; ++i ){
        A_row_norms[i] = std::abs(A[i + 0 * lda]);
        for ( int j = 1; j < k; ++j ){
            A_row_norms[i] = std::abs(A[i + j*lda]) > A_row_norms[i] ? std::abs(A[i + j*lda]) : A_row_norms[i];
        }
    }

    // find inf norms of cols of B
    for ( int i = 0; i < n; ++i ){
        B_col_norms[i] = std::abs(B[0 + i * ldb]);
        for ( int j = 1; j < k; ++j ){
            B_col_norms[i] = std::abs(B[j + i*ldb]) > B_col_norms[i] ? std::abs(B[j + i*ldb]) : B_col_norms[i];
        }
    }

    // scale to yield unit norms
    for ( int i = 0; i < k; ++i ){
        for ( int j = 0; j < m; ++j ){
            A[j + i*lda] = A_row_norms[j] != 0.0 ? A[j + i*lda] / A_row_norms[j] : 0.0;
        }
        for ( int j = 0; j < n; ++j ){
            B[i + j*ldb] = B_col_norms[j] != 0.0 ? B[i + j*ldb] / B_col_norms[j] : 0.0;
        }
    }
#endif

#if defined(USE_CUDA)
    size_t size_A = lda * k * sizeof(double);
    size_t size_B = ldb * n * sizeof(double);
    size_t size_C = ldc * n * sizeof(double);

    cudaMalloc((void**)&d_A, size_A);
    cudaMalloc((void**)&d_B, size_B);
    cudaMalloc((void**)&d_C, size_C);
    
    cudaMemcpy(d_A, &A[0], size_A, cudaMemcpyHostToDevice);
    cudaMemcpy(d_B, &B[0], size_B, cudaMemcpyHostToDevice);
    cudaMemcpy(d_C, &C[0], size_C, cudaMemcpyHostToDevice);

    cublasDgemm(handle, opA, opB, m, n, k, &alpha, d_A, lda, d_B, ldb, &beta, d_C, ldc);

    cudaMemcpy(C, d_C, size_C, cudaMemcpyDeviceToHost);

#if CUBLAS_VERSION >= 130100
    fprintf(stderr, "dgemm m=%d n=%d k=%d emulation_mantissa_bits=%d\n", m, n, k, *emulation_bits);
    cudaFreeHost(emulation_bits);
#endif

    cudaFree(d_A);
    cudaFree(d_B);
    cudaFree(d_C);

    cublasDestroy(handle);
#else
    dgemm_(&transa, &transb, &m, &n, &k, &alpha, &A[0], &lda, &B[0], &ldb, &beta, &C[0], &ldc);
#endif

#if defined(OUTER_SCALING)
    // unscale C
    for ( int i = 0; i < m; ++i ){
        for ( int j = 0; j < n; ++j ){
            C[i + j*ldc] = A_row_norms[i] * C[i + j*ldc] * B_col_norms[j];
        }
    }
#endif

#if defined(INNER_SCALING) || defined(OUTER_SCALING)
    // restore prescaled A and B
    copy_matrix( m, k, &A[0], lda, &A_prescaled[0], lda );
    copy_matrix( k, n, &B[0], ldb, &B_prescaled[0], ldb );
#endif

#if defined(VERBOSE)
    printf("C matrix:\n");
    print_matrix_to_stdout_sci(m, n, &C[0], ldc);
#endif

    return;
}