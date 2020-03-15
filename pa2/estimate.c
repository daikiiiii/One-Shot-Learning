#include <string.h>
#include <stdio.h>
#include <stdlib.h>

double ** transpose(double ** matrix, double ** transpose, int rows, int cols){
  int i, j;

  for (i = 0; i < cols; i++) {
    for (j = 0; j < rows; j++){
      transpose[i][j] = matrix[j][i];
    }
  }

  return transpose;

}

void printPriceMatrix(double ** matrix, int rows, int cols) {
    
  int i, j;
  for (i = 0; i < rows; i++) {
    for (j = 0; j < cols; j++){
      printf("%.0f", matrix[i][j]);  
    }
	printf("\n");
  }
}

double ** inverse(double ** matrix, int rows, int cols) {

  //printf("do you break inside the inverse?\n");

    int p , i, j;
    double ** identity_matrix = (double **)malloc(rows * sizeof(double *));
    for (i = 0; i < rows; i++) {
        identity_matrix[i] = malloc(rows * sizeof(double));
    }
    
    for (i = 0; i < rows; i++) {
        for (j = 0; j < cols; j++) {
            if (i == j) {
                identity_matrix[i][j] = 1;
            } else {
                identity_matrix[i][j] = 0;
            }
        }
    }
    
    // printf("made it past the identity matrix\n");
    
    // This is where the implementation of gaussian elimination will occur

    int ct;

    double f;

    for (p = 0; p < rows; p++) {
        f = matrix[p][p];
        // this for loop divides every element in row p by f
        for (ct = 0; ct < rows; ct++) {
            matrix[p][ct] /= f;
            identity_matrix[p][ct] /= f;
        }
        for (i = p + 1; i < rows; i++) {
            f = matrix[i][p];
            for (ct = 0; ct < rows; ct++) {
                matrix[i][ct] -= (f * matrix[p][ct]);
                identity_matrix[i][ct] -= (f * identity_matrix[p][ct]);
            }
        }
    }

    // printf("made it past the upper triangular setup\n");

    for (p = rows - 1; p >= 0; p--) {
        for (i = p-1; i >= 0; i--) {
	  // printf("made it through bois\n");
	    f = matrix[i][p];
            for (ct = 0; ct < rows; ct++) {
	      // printf("made it rhough the next one bois\n");
                matrix[i][ct] -= (f * matrix[p][ct]);
                identity_matrix[i][ct] -= (f * identity_matrix[p][ct]); 
            }
        }
    }
    
    // printf("or is c just an asshole\n");

    return identity_matrix;

}


double ** multiply(double ** matrix1, double ** matrix2, double ** result, int rows, int cols, int cols1) {

  int i, j, k;

  for (i = 0; i < rows; i++) {
    for (j = 0; j < cols; j++) {
      for (k = 0; k < cols1; k++) {
	 result[i][j] += matrix1[i][k] * matrix2[k][j];
      }
    }
  }
  
  return result;

}


void printMatrix(double ** matrix, int rows, int cols) {

    int i, j;
    for (i = 0; i < rows; i++) {
        for (j = 0; j < cols; j++) {
            printf("%lf ", matrix[i][j]);
        }
        printf("\n");
    }
}

double ** insertZeroes(double ** matrix, int rows, int cols) {
  
  int i, j;
  for (i = 0; i < rows; i++) {
    for (j = 0; j < cols; j++) {
      matrix[i][j] = 0;
    }
  }

  return matrix;

}

int main(int argc, char ** argv) {
    FILE *file1;
    file1 = fopen(argv[1], "r");

    int i, j, num_of_attributes, num_of_houses;

    char *train = malloc(7*sizeof(char));
    strcpy(train, "");
    fscanf(file1, " %s", train);
    fscanf(file1, " %d", &num_of_attributes);
    fscanf(file1, " %d", &num_of_houses);
   
    //printf("train: %s\n", train);
    //printf("num of attributes: %d\n", num_of_attributes);
    //printf("num of houses: %d\n", num_of_houses);

    double ** matrix_x = malloc( num_of_houses * sizeof(double *));
    double ** vector_y = malloc( num_of_houses * sizeof(double *));
    double ** vector_w = malloc( (num_of_attributes + 1) * sizeof(double*));

    for (i = 0; i < num_of_houses; i++) {
        matrix_x[i] = malloc((num_of_attributes + 1) * sizeof(double));
	vector_y[i] = malloc(sizeof(double));
    }

    for (i = 0; i < num_of_attributes + 1; i++) {
      vector_w[i] = malloc(sizeof(double));
    }

    matrix_x = insertZeroes(matrix_x, num_of_houses, num_of_attributes + 1);
    vector_y = insertZeroes(vector_y, num_of_houses, 1);
    vector_w = insertZeroes(vector_w, num_of_attributes + 1, 1);

    // loops through the given data points, the fscanf inside the for loop is 
    // to input numbers into X, accounting for the 0th column of 1s. Should
    // loop only four times, leaving the next scan for Y, which will occur outside
    // the nested for loop, but inside the parent for loop. 

    //printf("do you reach the loop?\n");

    for (i = 0; i < num_of_houses; i++) {
      //printf("breaks from reading the input of the file\n");
        //fscanf(file1, "%lf", matrix_x[i][0]);
        matrix_x[i][0] = 1;
        for (j = 1; j < num_of_attributes + 1; j++) {
	  //printf("how many loops?\n");
            fscanf(file1, "%lf", &matrix_x[i][j]);
        }
        fscanf(file1, "%lf", &vector_y[i][0]);
    }
    
    //printf("X: \n");
    //printMatrix(matrix_x, num_of_houses, num_of_attributes + 1);

    //printf("Y: \n");
    //printMatrix(vector_y, num_of_houses, 1);

    double ** transpose_x = malloc((num_of_attributes+1) * sizeof(double *));

    for (i = 0; i < num_of_attributes + 1; i++) {
      transpose_x[i] = malloc(num_of_houses * sizeof(double));
    }

    transpose_x = insertZeroes(transpose_x, num_of_attributes + 1, num_of_houses);

    transpose_x = transpose(matrix_x, transpose_x,num_of_houses, num_of_attributes+1);

    // printf("Transpose of X: \n");
    // printMatrix(transpose_x, num_of_attributes + 1, num_of_houses);

    double ** product_x = malloc((num_of_attributes + 1)*sizeof(double *));
    for (i = 0; i < num_of_attributes+1; i++) {
      product_x[i] = malloc((num_of_attributes + 1) * sizeof(double));
    }

    product_x = insertZeroes(product_x, num_of_attributes + 1, num_of_attributes + 1);

    product_x = multiply(transpose_x, matrix_x, product_x, num_of_attributes + 1, num_of_attributes + 1, num_of_houses);

    //printf("X^T(X): \n");
    //printMatrix(product_x, num_of_attributes + 1, num_of_attributes + 1);

    
    double ** inverse_x = malloc((num_of_attributes + 1) * sizeof(double *));
    for (i = 0; i < num_of_attributes+1; i++) {
      inverse_x[i] = malloc((num_of_attributes + 1) * sizeof(double));
    }

    inverse_x = insertZeroes(inverse_x, num_of_attributes + 1, num_of_attributes + 1);

    inverse_x = inverse(product_x, num_of_attributes + 1, num_of_attributes + 1);

    //printf("inverse of product: \n");
    //printMatrix(inverse_x, num_of_attributes+1, num_of_attributes+1);
 
    // by this point, all functions have been checked, and all seem to work. if it result isnt correct, come back here and check each
    // function call and check for possible edge cases
   
    double ** result_x = malloc((num_of_attributes + 1) * sizeof(double *));
    for (i = 0; i < num_of_attributes + 1; i++) {
        result_x[i] = malloc(num_of_houses * sizeof(double));
    } 

    result_x = insertZeroes(result_x, num_of_attributes + 1, num_of_houses);

    result_x = multiply(inverse_x, transpose_x, result_x, num_of_attributes + 1,num_of_houses, num_of_attributes + 1);

    vector_w = multiply(result_x, vector_y, vector_w, num_of_attributes + 1, 1, num_of_houses);

    fclose(file1);

    // ----- SHOULD BE DONE WITH TRAINING DATA SET ----------

    FILE * file2;
    file2 = fopen(argv[2], "r");

    i = 0, j = 0;
    int num_of_attributes_2 = 0, num_of_houses_2;

    char *data = malloc(7 * sizeof(char));
    fscanf(file2, " %s", data);
    fscanf(file2, " %d", &num_of_attributes_2);
    fscanf(file2, " %d", &num_of_houses_2);

    if (num_of_attributes != num_of_attributes_2) {
      printf("error\n");
      return 0;
    }

    //printf("att2: %d\n", num_of_attributes_2);
    //printf("ho2: %d\n", num_of_houses_2);

    double ** estimator_x = malloc(num_of_houses_2 * sizeof(double *));
    double ** estimator_y = malloc(num_of_houses_2 * sizeof(double *));

    for (i = 0; i < num_of_houses_2; i++) {
      estimator_x[i] = malloc((num_of_attributes_2 + 1) * sizeof(double));
      estimator_y[i] = malloc(sizeof(double));
    }

    estimator_x = insertZeroes(estimator_x, num_of_houses_2, num_of_attributes_2 + 1);
    estimator_y = insertZeroes(estimator_y, num_of_houses_2, 1);
    
    for (i = 0; i < num_of_houses_2; i++) {
      estimator_x[i][0] = 1;
      for (j = 1; j < num_of_attributes_2 + 1; j++) {
	fscanf(file2, "%lf", &estimator_x[i][j]);
      }
    }
    
    //printf("estimator_x: \n");
    //printMatrix(estimator_x, num_of_houses_2, num_of_attributes_2 + 1);

    estimator_y = multiply(estimator_x, vector_w, estimator_y, num_of_houses_2, 1, num_of_attributes_2+1);

    //printf("pls be to god: \n");
    printPriceMatrix(estimator_y, num_of_houses_2, 1);

    fclose(file2);

    //printf("reached the end/n");
    return 0;

}
