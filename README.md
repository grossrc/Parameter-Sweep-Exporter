# Overview
This program assists the user batch export combinations of parameterized designs in the Fusion 360 design software.

Without this program, the user must manually change the parameters driving the model to update then individually save each file (.STL or .STEP). This can be very time consuming, and for certain batch exporting requirements, it's prohibitive. 

This software solves this issue by:
- Automatically exporting bodies as .STEP/.STL files programatically
- Saving the exported files to a batch file folder
- Choosing the interval you want your parameter to be and the number of steps 
    - e.g. Radius should be between 1 mm and 2 mm in 5 increments (exported as 1, 1.25, 1.5, 1.75, 2)
- Automatically computing and assigning compinations of multiple parameter sweeps
    - e.g. sweep radius between 1 and 2mm and sweep length between 5 and 6mm
    - 4 models will export with radii and length: 1/5mm, 1/6mm, 2/5mm, 2/6mm
- Integrating into Fusion's native program environment.
- Custom naming schemes

[![➡️YouTube video Demo⬅️](https://img.youtube.com/vi/IrVTPpV2GpY/0.jpg)](https://youtu.be/IrVTPpV2GpY)

# Importing the program to Fusion
To import this program to Fusion, follow these quick steps:
1) Clone the repo and extract the folder.
2) In Fusion go to `Utilities > Add-Ins` and click the icon. It should look like this:
![alt text](/graphics/Screenshot%202026-02-10%20163238.png)
3) In the Add-in window, click the plus symbol. Then click `Script or add-in from device` and select the program folder.
4) Click the dropdown on utilities and run the program in your file that you want to export.
![alt text](/graphics/Screenshot%202026-02-10%20163830.png)


# Using the program
NOTE: To use this program, you must have a parameterized model. In other words, changing your parameter(s) of interest will automatically update the model reflecting that specific change. If you are unfamiliar with parameterization, please find documentation on that before using the program.